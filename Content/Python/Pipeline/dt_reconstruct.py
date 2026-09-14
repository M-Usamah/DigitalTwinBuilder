"""Rebuild the photographed/filmed scene as a textured 3D mesh.

This is the Instagram-style path: the pixels of the input become the twin,
instead of dropping in a hardcoded office or hotel floor plan.

Depth: Depth Anything V2 Small (fits an RTX 3050 Ti 4 GB). If the model is
unavailable, a camera-plane fallback still warps the photo into orbitable 3D.
"""

from __future__ import annotations

import os
from pathlib import Path

import cv2
import numpy as np

_DEPTH_PIPE = None
_DEPTH_SOURCE = "none"


def _progress(fn, pct, msg):
    if fn:
        fn(pct, msg)
    else:
        print("PROGRESS:{}|{}".format(pct, msg), flush=True)


def _load_depth_pipe():
    global _DEPTH_PIPE, _DEPTH_SOURCE
    if _DEPTH_PIPE is not None or _DEPTH_SOURCE == "failed":
        return _DEPTH_PIPE
    os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")
    try:
        from PIL import Image
        from transformers import pipeline
    except Exception as exc:
        print("transformers unavailable ({}) — plane depth".format(exc), flush=True)
        _DEPTH_SOURCE = "failed"
        return None
    model_id = os.environ.get(
        "DT_DEPTH_MODEL", "depth-anything/Depth-Anything-V2-Small-hf"
    ).strip()
    try:
        _DEPTH_PIPE = pipeline(
            task="depth-estimation",
            model=model_id,
            device=0 if _cuda_ok() else -1,
        )
        _DEPTH_SOURCE = model_id
        print("Depth model: {}".format(model_id), flush=True)
        return _DEPTH_PIPE
    except Exception as exc:
        print("Depth model load failed ({}) — plane depth".format(exc), flush=True)
        _DEPTH_SOURCE = "failed"
        return None


def _cuda_ok() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def estimate_depth(bgr: np.ndarray) -> tuple[np.ndarray, str]:
    """Return metric-style Z (meters, larger = farther)."""
    h, w = bgr.shape[:2]
    pipe = _load_depth_pipe()
    if pipe is not None:
        from PIL import Image

        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        out = pipe(Image.fromarray(rgb))
        raw = np.asarray(out["depth"], dtype=np.float32)
        if raw.shape[0] != h or raw.shape[1] != w:
            raw = cv2.resize(raw, (w, h), interpolation=cv2.INTER_LINEAR)
        d = raw.astype(np.float32)
        d = d - float(np.percentile(d, 1))
        d = d / max(float(np.percentile(d, 99) - 0.0), 1e-6)
        d = np.clip(d, 0.0, 1.0)
        d8 = (d * 255.0).astype(np.uint8)
        d8 = cv2.medianBlur(d8, 9)
        d8 = cv2.bilateralFilter(d8, 9, 55, 55)
        h, w = d8.shape
        low = cv2.resize(d8, (max(32, w // 6), max(32, h // 6)), interpolation=cv2.INTER_AREA)
        low = cv2.GaussianBlur(low, (0, 0), 1.15)
        low = cv2.resize(low, (w, h), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255.0
        hi = d8.astype(np.float32) / 255.0
        close = np.clip(0.75 * low + 0.25 * hi, 0.0, 1.0)
        # Keep metric Z for optional unproject; 3D-photo path uses `close` via depth.
        z = 0.85 + (1.0 - close) * 2.4
        return z.astype(np.float32), _DEPTH_SOURCE
    ys = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]
    z = 0.85 + 2.6 * (1.0 - ys) ** 1.35
    z = np.repeat(z, w, axis=1)
    return z, "plane"


def _unproject(depth: np.ndarray, stride: int, fx: float, fy: float, cx: float, cy: float):
    h, w = depth.shape
    ys, xs = np.mgrid[0:h:stride, 0:w:stride]
    z = depth[ys, xs]
    x = (xs - cx) * z / fx
    y = (ys - cy) * z / fy
    return np.stack([x, y, z], axis=-1), xs, ys


def _cam_to_yup() -> np.ndarray:
    """OpenCV camera (X right, Y down, Z forward) → Y-up (X right, Y up, Z forward)."""
    return np.array([[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64)


def _align_floor(cam_xyz: np.ndarray, ys: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Keep the photo facing the camera. Only a light floor tilt from the bottom of the image."""
    to_yup = _cam_to_yup()
    h = int(ys.max()) + 1 if ys.size else 1
    pts = cam_xyz.reshape(-1, 3)
    ypix = ys.reshape(-1)
    valid = np.isfinite(pts).all(axis=1) & (pts[:, 2] > 0.2)
    # Bottom of the frame is almost always floor in indoor shots.
    floor_pix = valid & (ypix >= 0.72 * h)
    floor_pts = pts[floor_pix]
    if len(floor_pts) < 80:
        return to_yup, np.zeros(3)
    nrm, offs = _ransac_plane(floor_pts, iters=60)
    # Floor normal in camera space should be mostly -Y (up toward camera).
    if nrm[1] > 0:
        nrm = -nrm
    # Ignore near-vertical "floors" (walls) — those stood the photo on its edge.
    if abs(nrm[1]) < 0.55:
        return to_yup, np.zeros(3)
    up = np.array([0.0, -1.0, 0.0])
    R_tilt = _rotation_between(nrm, up)
    R = to_yup @ R_tilt
    sample = (R @ floor_pts[:: max(1, len(floor_pts) // 400)].T).T
    shift = np.array([0.0, -float(np.median(sample[:, 1])), 0.0])
    return R, shift


def _ransac_plane(pts: np.ndarray, iters: int = 80):
    best_in = -1
    best_n = np.array([0.0, 1.0, 0.0])
    best_o = 0.0
    n = len(pts)
    rng = np.random.default_rng(0)
    for _ in range(iters):
        idx = rng.choice(n, 3, replace=False)
        p0, p1, p2 = pts[idx]
        nrm = np.cross(p1 - p0, p2 - p0)
        ln = np.linalg.norm(nrm)
        if ln < 1e-8:
            continue
        nrm = nrm / ln
        offs = -float(np.dot(nrm, p0))
        dist = np.abs(pts @ nrm + offs)
        nin = int((dist < 0.04 * (np.median(pts[:, 2]) + 0.2)).sum())
        if nin > best_in:
            best_in = nin
            best_n, best_o = nrm, offs
    return best_n, best_o


def _rotation_between(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a = a / max(np.linalg.norm(a), 1e-8)
    b = b / max(np.linalg.norm(b), 1e-8)
    v = np.cross(a, b)
    c = float(np.dot(a, b))
    if c < -0.999:
        axis = np.cross(a, np.array([1.0, 0.0, 0.0]))
        if np.linalg.norm(axis) < 1e-6:
            axis = np.cross(a, np.array([0.0, 1.0, 0.0]))
        axis = axis / np.linalg.norm(axis)
        K = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
        return np.eye(3) + 2 * K @ K
    s = np.linalg.norm(v)
    if s < 1e-8:
        return np.eye(3)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K * ((1 - c) / (s * s))


def reconstruct_frame(bgr: np.ndarray, out_dir: Path, progress=None, stride: int = 2) -> dict | None:
    """Front-facing 3D photo of this frame (Y-up: X right, Y height, Z depth)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    h, w = bgr.shape[:2]
    stride = max(int(stride), 1)
    stride = max(stride, int(np.ceil(max(h, w) / 480.0)))
    _progress(progress, 71, "Estimating scene depth...")
    depth, src = estimate_depth(bgr)
    # Depth Anything Z: larger = farther. Invert to closeness for a postcard relief.
    zmin, zmax = float(np.percentile(depth, 2)), float(np.percentile(depth, 98))
    close = np.clip(1.0 - (depth - zmin) / max(zmax - zmin, 1e-6), 0.0, 1.0)

    width = 16.0
    height = width * float(h) / float(max(w, 1))
    relief = 2.6

    ys, xs = np.mgrid[0:h:stride, 0:w:stride]
    gh, gw = ys.shape
    cl = close[ys, xs]
    X = (xs.astype(np.float32) / max(w - 1, 1) - 0.5) * width
    Y = (1.0 - ys.astype(np.float32) / max(h - 1, 1)) * height
    Z = (1.0 - cl) * relief
    verts_yup = np.stack([X, Y, Z], axis=-1)

    tex = out_dir / "scene_texture.jpg"
    cv2.imwrite(str(tex), bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 92])

    obj = out_dir / "scene_mesh.obj"
    mtl = out_dir / "scene_mesh.mtl"
    mtl.write_text(
        "newmtl scene\nKd 1 1 1\nKa 0.04 0.04 0.04\nmap_Kd {}\n".format(tex.name),
        encoding="utf-8",
    )
    _progress(progress, 78, "Building textured scene mesh...")
    nvert = gh * gw
    idx = np.arange(1, nvert + 1, dtype=np.int32).reshape(gh, gw)
    v_lines = [
        "# Digital Twin 3D photo",
        "# coord y_up",
        "mtllib {}".format(mtl.name),
        "usemtl scene",
    ]
    flat = verts_yup.reshape(-1, 3)
    v_lines.extend("v {:.5f} {:.5f} {:.5f}".format(float(p[0]), float(p[1]), float(p[2])) for p in flat)
    uu = (xs.astype(np.float32) + 0.5) / w
    vv = 1.0 - (ys.astype(np.float32) + 0.5) / h
    vt_lines = ["vt {:.6f} {:.6f}".format(float(u), float(v)) for u, v in zip(uu.ravel(), vv.ravel())]
    a = idx[:-1, :-1]
    b = idx[:-1, 1:]
    c = idx[1:, 1:]
    d = idx[1:, :-1]
    # Tear only at huge depth jumps so the photo stays a solid sheet, not shredded strips.
    jump = np.maximum.reduce(
        [
            np.abs(Z[:-1, :-1] - Z[:-1, 1:]),
            np.abs(Z[:-1, :-1] - Z[1:, :-1]),
            np.abs(Z[:-1, 1:] - Z[1:, 1:]),
            np.abs(Z[1:, :-1] - Z[1:, 1:]),
        ]
    )
    keep = jump < (0.55 * relief)
    faces = []
    for ia, ib, ic, idd in zip(a[keep].ravel(), b[keep].ravel(), c[keep].ravel(), d[keep].ravel()):
        faces.append("f {}/{} {}/{} {}/{}".format(ia, ia, idd, idd, ic, ic))
        faces.append("f {}/{} {}/{} {}/{}".format(ia, ia, ic, ic, ib, ib))
    if nvert < 40 or not faces:
        print("Scene mesh too sparse", flush=True)
        return None
    obj.write_text("\n".join(v_lines + vt_lines + faces) + "\n", encoding="utf-8")

    mn = flat.min(axis=0)
    mx = flat.max(axis=0)
    center = 0.5 * (mn + mx)
    size = mx - mn
    print(
        "Scene mesh: {} verts, {} faces, depth={}, span=({:.1f},{:.1f},{:.1f})".format(
            nvert, len(faces), src, size[0], size[1], size[2]
        ),
        flush=True,
    )
    fx = fy = 0.90 * float(max(w, h))
    return {
        "obj_path": str(obj.resolve()),
        "tex_path": str(tex.resolve()),
        "depth_source": src,
        "coord": "y_up",
        "center": [float(center[0]), float(center[1]), float(center[2])],
        "size": [float(size[0]), float(size[1]), float(size[2])],
        "R": _cam_to_yup().tolist(),
        "shift": [0.0, 0.0, 0.0],
        "scale": 1.0,
        "width": float(width),
        "height": float(height),
        "relief": float(relief),
        "y_floor": 0.0,
        "x_center": 0.0,
        "z_near": 0.0,
        "fx": fx,
        "fy": fy,
        "cx": 0.5 * (w - 1),
        "cy": 0.5 * (h - 1),
        "stride": stride,
        "depth": depth,
        "camera_eye": {"x": 0.0, "y": -1.65, "z": 0.08},
        "cam_dist": 8.0,
    }


def unproject_pixel(u: float, v: float, depth: np.ndarray, recon: dict) -> tuple[float, float, float]:
    """Image pixel -> Y-up XYZ matching the 3D-photo mesh."""
    h, w = depth.shape
    ui = float(np.clip(u, 0, w - 1))
    vi = float(np.clip(v, 0, h - 1))
    zmin, zmax = float(np.percentile(depth, 2)), float(np.percentile(depth, 98))
    z = float(depth[int(round(vi)), int(round(ui))])
    close = float(np.clip(1.0 - (z - zmin) / max(zmax - zmin, 1e-6), 0.0, 1.0))
    width = float(recon.get("width", 16.0))
    height = float(recon.get("height", width * h / max(w, 1)))
    relief = float(recon.get("relief", 2.6))
    x = (ui / max(w - 1, 1) - 0.5) * width
    y = (1.0 - vi / max(h - 1, 1)) * height
    z_fwd = (1.0 - close) * relief
    return x, y, z_fwd


def desk_hull_xz(bgr: np.ndarray, det: dict, recon: dict | None, depth: np.ndarray | None) -> list[list[float]]:
    """Table footprint in XZ from the real silhouette (GrabCut + unproject)."""
    h, w = bgr.shape[:2]
    x1 = max(0, int(det["x1"]))
    y1 = max(0, int(det["y1"]))
    x2 = min(w, int(det["x2"]))
    y2 = min(h, int(det["y2"]))
    if x2 - x1 < 16 or y2 - y1 < 16:
        return []
    mask = np.zeros((h, w), np.uint8)
    rect = (x1, y1, max(1, x2 - x1), max(1, y2 - y1))
    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)
    try:
        cv2.grabCut(bgr, mask, rect, bgd, fgd, 3, cv2.GC_INIT_WITH_RECT)
        binm = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    except Exception:
        binm = np.zeros((h, w), np.uint8)
        binm[y1:y2, x1:x2] = 255
    cnts, _ = cv2.findContours(binm, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return []
    cnt = max(cnts, key=cv2.contourArea)
    peri = cv2.arcLength(cnt, True)
    approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
    if len(approx) < 3:
        return []
    hull = []
    for p in approx.reshape(-1, 2):
        if recon is not None and depth is not None:
            x, y, z = unproject_pixel(float(p[0]), float(p[1]), depth, recon)
            hull.append([float(x), float(z)])
        else:
            hull.append(
                [
                    float((float(p[0]) / w - 0.5) * 22.0),
                    float((0.85 - float(p[1]) / h) * 18.0),
                ]
            )
    return hull
