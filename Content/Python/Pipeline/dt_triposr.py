"""Crop YOLO boxes and run TripoSR (stabilityai/TripoSR) to make per-object meshes."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import cv2

HERE = Path(__file__).resolve().parent


def find_triposr_root() -> Path | None:
    plugin_copy = HERE / "TripoSR"
    if (plugin_copy / "run.py").is_file():
        return plugin_copy
    for parent in Path(__file__).resolve().parents:
        candidate = (
            parent
            / "Content"
            / "python"
            / "AutomatedSyntheticDataPipeline"
            / "03_MeshFromImage"
            / "TripoSR"
        )
        if (candidate / "run.py").is_file():
            return candidate
    env = os.environ.get("TRIPOSR_ROOT", "").strip()
    if env:
        p = Path(env)
        if (p / "run.py").is_file():
            return p
    return None


def _save_crop(frame_path: Path, det: dict, dest: Path, pad: int = 16) -> Path | None:
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


def _mesh_file(out_dir: Path) -> Path | None:
    for cand in (out_dir / "0" / "mesh.obj", out_dir / "mesh.obj"):
        if cand.is_file() and cand.stat().st_size > 256:
            return cand
    found = list(out_dir.rglob("mesh.obj"))
    return found[0] if found else None


def run_triposr(crop: Path, out_dir: Path, triposr_root: Path) -> Path | None:
    out_dir.mkdir(parents=True, exist_ok=True)
    existing = _mesh_file(out_dir)
    if existing:
        return existing
    cmd = [
        sys.executable,
        str(triposr_root / "run.py"),
        str(crop),
        "--output-dir",
        str(out_dir),
        "--chunk-size",
        "1024",
        "--mc-resolution",
        "96",
        "--model-save-format",
        "obj",
    ]
    print("TripoSR {} -> {}".format(crop.name, out_dir.name), flush=True)
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    attempts = [cmd, cmd + ["--no-remove-bg"]]
    for attempt in attempts:
        result = subprocess.run(attempt, cwd=str(triposr_root), env=env, capture_output=False)
        mesh = _mesh_file(out_dir)
        if result.returncode == 0 and mesh is not None:
            return mesh
        print(
            "TripoSR attempt failed for {} (exit {})".format(crop.name, result.returncode),
            flush=True,
        )
    return None


def attach_triposr_meshes(
    items: list[dict],
    images_dir: Path,
    layout_frame: str | None,
    work_dir: Path,
    progress=None,
) -> list[dict]:
    """
    For each unique label without a library mesh, crop and run TripoSR.
    Broken photo-reconstruction meshes are not used for furniture.
    """
    skip = {
        "desk",
        "table",
        "chair",
        "bed",
        "lamp",
        "nightstand",
        "pillow",
        "couch",
        "laptop",
        "monitor",
        "keyboard",
        "mouse",
        "bottle",
        "backpack",
        "plant",
        "mirror",
        "curtain",
        "paper",
        "book",
        "cell phone",
    }
    if all(it.get("mesh_path") or it["label"] in skip for it in items):
        print("TripoSR skipped — using furniture library meshes", flush=True)
        if progress:
            progress(88, "Using furniture library meshes")
        return items
    root = find_triposr_root()
    if root is None:
        msg = "TripoSR not found — schematic furniture only"
        print(msg, flush=True)
        if progress:
            progress(72, msg)
        return items
    if progress:
        progress(71, "TripoSR: {}".format(root))

    frame_path = None
    if layout_frame:
        frame_path = images_dir / layout_frame
        if not frame_path.is_file():
            frame_path = None
    if frame_path is None:
        frames = sorted(images_dir.glob("*.jpg")) + sorted(images_dir.glob("*.png"))
        frame_path = frames[0] if frames else None
    if frame_path is None:
        print("No layout frame for TripoSR crops", flush=True)
        return items

    crops_dir = work_dir / "crops"
    mesh_dir = work_dir / "triposr"
    crops_dir.mkdir(parents=True, exist_ok=True)
    mesh_dir.mkdir(parents=True, exist_ok=True)

    by_label: dict[str, dict] = {}
    for it in items:
        lab = it["label"]
        if it.get("mesh_path") or lab in skip or "x1" not in it:
            continue
        prev = by_label.get(lab)
        if prev is None or float(it.get("confidence", 0)) > float(prev.get("confidence", 0)):
            by_label[lab] = it
    if not by_label:
        print("TripoSR skipped — no remaining labels", flush=True)
        return items

    labels = list(by_label.keys())
    meshes: dict[str, str] = {}
    for i, lab in enumerate(labels):
        it = by_label[lab]
        if progress:
            progress(72 + int(16 * (i / max(len(labels), 1))), "TripoSR mesh: {}".format(lab))
        crop = _save_crop(frame_path, it, crops_dir / "{}.png".format(lab))
        if crop is None:
            print("Could not crop {}".format(lab), flush=True)
            continue
        mesh = run_triposr(crop, mesh_dir / lab, root)
        if mesh is not None:
            meshes[lab] = str(mesh.resolve())
            print("Mesh OK {}: {}".format(lab, mesh), flush=True)

    for it in items:
        mp = meshes.get(it["label"])
        if mp:
            it["mesh_path"] = mp
    if progress:
        progress(88, "TripoSR meshes: {}/{} labels".format(len(meshes), len(labels)))
    return items
