"""Image-to-3D via TRELLIS.2 (microsoft/TRELLIS.2-4B).

Local TRELLIS.2 needs ~24 GB VRAM and Linux CUDA kernels, so this calls the
official Hugging Face Space and writes GLB + OBJ the Unreal spawn can import.
"""

from __future__ import annotations

import base64
import os
import re
import shutil
from pathlib import Path

import cv2

HERE = Path(__file__).resolve().parent
SPACE_ID = os.environ.get("DT_TRELLIS2_SPACE", "microsoft/TRELLIS.2").strip()
RESOLUTION = os.environ.get("DT_TRELLIS2_RES", "512").strip() or "512"

MESH_LABELS = {
    "chair",
    "desk",
    "table",
    "bed",
    "couch",
    "lamp",
    "nightstand",
    "monitor",
    "plant",
    "laptop",
    "backpack",
    "accent_chair",
    "vanity_chair",
    "vanity",
    "pillow",
    "mirror",
}


def _save_crop(frame_path: Path, det: dict, dest: Path, pad: int = 24) -> Path | None:
    img = cv2.imread(str(frame_path))
    if img is None:
        return None
    h, w = img.shape[:2]
    x1 = max(0, int(float(det["x1"])) - pad)
    y1 = max(0, int(float(det["y1"])) - pad)
    x2 = min(w, int(float(det["x2"])) + pad)
    y2 = min(h, int(float(det["y2"])) + pad)
    if x2 <= x1 + 8 or y2 <= y1 + 8:
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(dest), img[y1:y2, x1:x2])
    return dest


def _dump_preview_html(html: str, dest: Path, max_frames: int = 4) -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    frames = []
    for i, m in enumerate(re.finditer(r"data:image/(jpeg|jpg|png);base64,([A-Za-z0-9+/=]+)", html or "")):
        if i >= max_frames:
            break
        ext = "jpg" if m.group(1) in {"jpeg", "jpg"} else "png"
        path = dest / "preview_{:02d}.{}".format(i, ext)
        path.write_bytes(base64.b64decode(m.group(2)))
        frames.append(path)
    return frames


def _glb_to_obj(glb_path: Path, obj_path: Path) -> Path | None:
    try:
        import trimesh
    except ImportError:
        print("trimesh missing — keeping GLB {}".format(glb_path), flush=True)
        return None
    loaded = trimesh.load(str(glb_path), force="scene")
    meshes = []
    if isinstance(loaded, trimesh.Scene):
        for geom in loaded.dump():
            if hasattr(geom, "faces") and getattr(geom, "faces", None) is not None:
                meshes.append(geom)
    elif hasattr(loaded, "faces"):
        meshes.append(loaded)
    if not meshes:
        return None
    mesh = trimesh.util.concatenate(meshes) if len(meshes) > 1 else meshes[0]
    obj_path.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(str(obj_path))
    if obj_path.is_file() and obj_path.stat().st_size > 256:
        return obj_path
    return None


def _image_arg(path: Path):
    from gradio_client import handle_file

    return handle_file(str(path))


def _remove_background(crop: Path, dest: Path) -> Path:
    """Cut the object out locally so the Space does not spend ZeroGPU on RMBG."""
    try:
        from rembg import remove
        from PIL import Image
    except ImportError:
        return crop
    img = Image.open(crop).convert("RGB")
    cut = remove(img)
    dest.parent.mkdir(parents=True, exist_ok=True)
    cut.save(dest)
    return dest if dest.is_file() else crop


def run_trellis2(crop: Path, out_dir: Path) -> Path | None:
    """Generate one textured mesh from a crop. Returns OBJ if possible, else GLB."""
    out_dir.mkdir(parents=True, exist_ok=True)
    existing_obj = out_dir / "mesh.obj"
    existing_glb = out_dir / "mesh.glb"
    if existing_obj.is_file() and existing_obj.stat().st_size > 256:
        return existing_obj
    if existing_glb.is_file() and existing_glb.stat().st_size > 256:
        obj = _glb_to_obj(existing_glb, existing_obj)
        return obj or existing_glb

    from gradio_client import Client

    print("TRELLIS.2 {} -> {}".format(crop.name, out_dir.name), flush=True)
    cut = _remove_background(crop, out_dir / "crop_nobg.png")
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN") or None
    client = Client(SPACE_ID, hf_token=token)
    try:
        client.predict(api_name="/start_session")
    except Exception:
        pass
    image_in = _image_arg(cut)

    seed = int(os.environ.get("DT_TRELLIS2_SEED", "1"))
    html = client.predict(
        image_in,
        seed,
        RESOLUTION,
        7.5,
        0.7,
        12,
        5.0,
        7.5,
        0.5,
        12,
        3.0,
        1.0,
        0.0,
        12,
        3.0,
        api_name="/image_to_3d",
    )
    if isinstance(html, (list, tuple)):
        html = next((x for x in html if isinstance(x, str) and "<" in x), html[-1] if html else "")
    previews = _dump_preview_html(str(html or ""), out_dir / "previews")
    if previews:
        print("TRELLIS.2 preview: {}".format(previews[0]), flush=True)

    glb_out = client.predict(100000, 1024, api_name="/extract_glb")
    glb_src = None
    if isinstance(glb_out, (list, tuple)):
        glb_src = next((p for p in glb_out if p), None)
    else:
        glb_src = glb_out
    if isinstance(glb_src, dict):
        glb_src = glb_src.get("path") or glb_src.get("url")
    if not glb_src or not os.path.isfile(str(glb_src)):
        print("TRELLIS.2 extract_glb returned no file for {}".format(crop.name), flush=True)
        return None
    shutil.copy2(str(glb_src), existing_glb)
    obj = _glb_to_obj(existing_glb, existing_obj)
    return obj or existing_glb


def attach_trellis2_meshes(
    items: list[dict],
    images_dir: Path,
    layout_frame: str | None,
    work_dir: Path,
    progress=None,
) -> list[dict]:
    """Crop each unique furniture label and replace schematic meshes with TRELLIS.2."""
    max_labels = int(os.environ.get("DT_TRELLIS2_MAX", "6"))
    frame_path = None
    if layout_frame:
        frame_path = images_dir / layout_frame
        if not frame_path.is_file():
            frame_path = None
    if frame_path is None:
        frames = sorted(images_dir.glob("*.jpg")) + sorted(images_dir.glob("*.png"))
        frame_path = frames[0] if frames else None
    if frame_path is None:
        print("TRELLIS.2 skipped — no layout frame", flush=True)
        return items

    by_label: dict[str, dict] = {}
    for it in items:
        lab = it["label"]
        if lab not in MESH_LABELS or "x1" not in it:
            continue
        prev = by_label.get(lab)
        if prev is None or float(it.get("confidence", 0)) > float(prev.get("confidence", 0)):
            by_label[lab] = it
    labels = list(by_label.keys())[: max(1, max_labels)]
    if not labels:
        print("TRELLIS.2 skipped — no furniture crops", flush=True)
        return items

    crops_dir = work_dir / "crops"
    mesh_dir = work_dir / "trellis2"
    crops_dir.mkdir(parents=True, exist_ok=True)
    mesh_dir.mkdir(parents=True, exist_ok=True)

    meshes: dict[str, str] = {}
    for i, lab in enumerate(labels):
        it = by_label[lab]
        if progress:
            progress(70 + int(18 * (i / max(len(labels), 1))), "TRELLIS.2 mesh: {}".format(lab))
        crop = _save_crop(frame_path, it, crops_dir / "{}.png".format(lab))
        if crop is None:
            print("Could not crop {}".format(lab), flush=True)
            continue
        try:
            mesh = run_trellis2(crop, mesh_dir / lab)
        except Exception as exc:
            msg = str(exc)
            print("TRELLIS.2 failed for {}: {}".format(lab, exc), flush=True)
            if progress:
                progress(88, "TRELLIS.2 failed: {}".format(msg[:120]))
            if "ZeroGPU quota" in msg or "exceeded" in msg.lower():
                break
            mesh = None
        if mesh is not None:
            meshes[lab] = str(mesh.resolve())
            print("TRELLIS.2 OK {}: {}".format(lab, mesh), flush=True)

    for it in items:
        mp = meshes.get(it["label"])
        if mp:
            it["mesh_path"] = mp
            it["mesh_source"] = "trellis2"
            it["use_prims"] = False
    if progress:
        progress(88, "TRELLIS.2 meshes: {}/{} labels".format(len(meshes), len(labels)))
    return items
