"""
Plugin-bundled Unreal export CLI (no project Content/python paths).

  py -3.12 export_unreal_scene.py --input <images|video|folder> --output <dir>

Prints PROGRESS: lines for the Unreal Output Log pump.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cv2
import numpy as np

import dt_detect as dtl
from dt_furniture import items_to_unreal_actors, local_furniture_prims, office_layout


def progress(pct: int, msg: str) -> None:
    print("PROGRESS:{}|{}".format(max(0, min(100, int(pct))), msg), flush=True)


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--extra", nargs="*", default=[])
    p.add_argument("--scene", default="auto")
    return p.parse_args()


def gather_image_list(primary: Path, extra: list[str]) -> tuple[str, list[Path]]:
    if primary.is_dir():
        files = [p for p in sorted(primary.iterdir()) if p.suffix.lower() in dtl.IMAGE_EXTS]
        return "images", files
    if primary.suffix.lower() in dtl.VIDEO_EXTS:
        return "video", [primary]
    if primary.suffix.lower() in dtl.IMAGE_EXTS:
        files = [primary]
        for e in extra:
            ep = Path(e)
            if ep.exists() and ep.suffix.lower() in dtl.IMAGE_EXTS:
                files.append(ep)
        return "images", files
    raise FileNotFoundError("Unsupported input: {}".format(primary))


def copy_images_to_dir(files: list[Path], dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for i, src in enumerate(files):
        out = dest / "frame_{:04d}.jpg".format(i)
        if src.suffix.lower() in {".jpg", ".jpeg"}:
            shutil.copy2(src, out)
        else:
            img = cv2.imread(str(src))
            if img is None:
                shutil.copy2(src, dest / "frame_{:04d}{}".format(i, src.suffix.lower()))
            else:
                cv2.imwrite(str(out), img)


def prim_top(label: str) -> float:
    prims = local_furniture_prims(label)
    return max(p["center"][1] + p["size"][1] * 0.5 for p in prims)


def bbox_area(d) -> float:
    return max(0.0, d["x2"] - d["x1"]) * max(0.0, d["y2"] - d["y1"])


def nms(dets, iou_thresh=0.28):
    by = {}
    for d in dets:
        by.setdefault(d["label"], []).append(d)
    kept = []
    for items in by.values():
        items = sorted(items, key=lambda x: -x["confidence"])
        used = [False] * len(items)
        for i, a in enumerate(items):
            if used[i]:
                continue
            kept.append(a)
            for j in range(i + 1, len(items)):
                if used[j]:
                    continue
                ax1, ay1, ax2, ay2 = a["x1"], a["y1"], a["x2"], a["y2"]
                b = items[j]
                ix1, iy1 = max(ax1, b["x1"]), max(ay1, b["y1"])
                ix2, iy2 = min(ax2, b["x2"]), min(ay2, b["y2"])
                inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
                area = (ax2 - ax1) * (ay2 - ay1) + (b["x2"] - b["x1"]) * (b["y2"] - b["y1"]) - inter
                if area > 1e-6 and inter / area >= iou_thresh:
                    used[j] = True
    return kept


def image_to_xz(det, w, h, span_x=22.0, span_z=18.0):
    cx = ((det["x1"] + det["x2"]) * 0.5) / max(w, 1)
    by = det["y2"] / max(h, 1)
    return (cx - 0.5) * span_x, (0.85 - by) * span_z


def on_desk_box(det, desk, pad=0.08) -> bool:
    if desk is None:
        return False
    cx = (det["x1"] + det["x2"]) * 0.5
    cy = (det["y1"] + det["y2"]) * 0.5
    ox1 = desk["x1"] - pad * (desk["x2"] - desk["x1"])
    ox2 = desk["x2"] + pad * (desk["x2"] - desk["x1"])
    oy1 = desk["y1"] - pad * (desk["y2"] - desk["y1"])
    oy2 = desk["y2"] + pad * (desk["y2"] - desk["y1"])
    return ox1 <= cx <= ox2 and oy1 <= cy <= oy2


SURFACE = {"laptop", "monitor", "keyboard", "mouse", "bottle", "book", "phone", "paper", "cup"}
CAPS = {
    "desk": 1,
    "table": 1,
    "chair": 4,
    "laptop": 2,
    "monitor": 1,
    "tv": 1,
    "keyboard": 1,
    "mouse": 1,
    "bottle": 2,
    "backpack": 1,
    "book": 2,
}


def detections_to_items(dets, img_w, img_h) -> list[dict]:
    dets = nms(dets)
    hosts = [d for d in dets if d["label"] in {"desk", "table"}]
    desk = max(hosts, key=bbox_area) if hosts else None
    cleaned = []
    for d in dets:
        lab = d["label"]
        if lab in {"desk", "table"}:
            if desk is None or d is not desk:
                continue
            d = {**d, "label": "desk"}
        if lab == "tv":
            d = {**d, "label": "monitor"}
        cleaned.append(d)

    placed = []
    for d in cleaned:
        x, z = image_to_xz(d, img_w, img_h)
        placed.append({**d, "X": x, "Z": z})

    by = {}
    for p in placed:
        by.setdefault(p["label"], []).append(p)
    kept = []
    for lab, items in by.items():
        items = sorted(items, key=lambda d: -d["confidence"])
        chosen = []
        for d in items:
            if any(math.hypot(d["X"] - c["X"], d["Z"] - c["Z"]) < 3.2 for c in chosen):
                continue
            chosen.append(d)
        kept.extend(chosen[: CAPS.get(lab, 2)])

    desks = [p for p in kept if p["label"] == "desk"]
    if desks:
        ox, oz = desks[0]["X"], desks[0]["Z"]
        for p in kept:
            p["X"] -= ox
            p["Z"] -= oz

    host_xz = (desks[0]["X"], desks[0]["Z"]) if desks else None
    desk_h = prim_top("desk") if desks else 0.0
    seq = {}
    items = []
    for p in kept:
        lab = p["label"]
        seq[lab] = seq.get(lab, 0) + 1
        lift = desk_h if (lab in SURFACE and on_desk_box(p, desk)) else 0.0
        yaw = 0.0
        if lab == "chair" and host_xz:
            dx = host_xz[0] - p["X"]
            dz = host_xz[1] - p["Z"]
            if abs(dx) + abs(dz) > 1e-4:
                yaw = math.degrees(math.atan2(-dx, dz))
        elif lab == "monitor":
            yaw = 180.0
        items.append(
            {
                "object_id": "{}_{:03d}".format(lab, seq[lab]),
                "label": lab,
                "X": p["X"],
                "Z": p["Z"],
                "yaw": yaw,
                "lift": lift,
                "confidence": p["confidence"],
            }
        )
    return items


def fallback_office_items() -> list[dict]:
    return office_layout()


def main():
    args = parse_args()
    progress(5, "Starting Digital Twin pipeline...")
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    media_dir = out / "media"
    if media_dir.exists():
        shutil.rmtree(media_dir)
    media_dir.mkdir(parents=True)

    kind, files = gather_image_list(args.input, args.extra)
    progress(10, "Input: {} ({} file(s))".format(kind, len(files)))

    images = out / "images"
    if images.exists():
        shutil.rmtree(images)
    progress(20, "Preparing frames...")
    if kind == "video":
        names = dtl.extract_keyframes(files[0], images, stride=4, max_frames=40)
        shutil.copy2(files[0], media_dir / files[0].name)
        progress(30, "Extracted {} keyframes".format(len(names)))
    else:
        copy_images_to_dir(files, images)
        for p in files:
            shutil.copy2(p, media_dir / p.name)
        names = [p.name for p in sorted(images.iterdir())]
        progress(30, "Copied {} images".format(len(names)))

    weights = ROOT / "yolov8s-world.pt"
    model_path = str(weights) if weights.is_file() else dtl.resolve_model_path()
    progress(35, "Loading YOLO-World...")
    try:
        yolo = dtl.load_detector(model_path, scene=args.scene or "auto")
    except Exception as exc:
        progress(36, "auto classes failed ({}); retry office vocab".format(exc))
        yolo = dtl.load_detector(model_path, scene="office")

    ann = out / "annotated"
    ann.mkdir(exist_ok=True)
    frames = []
    counts = {}
    img_paths = sorted(images.iterdir())
    for i, path in enumerate(img_paths[:16]):
        frame = cv2.imread(str(path))
        if frame is None:
            continue
        dets, plotted = dtl.detect_yolo(yolo, frame, conf=0.32, imgsz=960)
        cv2.imwrite(str(ann / path.name), plotted)
        h, w = frame.shape[:2]
        for d in dets:
            counts[d["label"]] = counts.get(d["label"], 0) + 1
        frames.append({"path": path, "dets": dets, "size": (w, h)})
        progress(40 + int(20 * (i + 1) / max(len(img_paths[:16]), 1)), "Detected {}".format(path.name))

    progress(62, "Building furniture from detections...")
    items = []
    layout_frame = None
    if frames:

        def score(f):
            dets = [d for d in f["dets"] if d["confidence"] >= 0.35] or f["dets"]
            labels = {d["label"] for d in dets}
            mean_c = float(np.mean([d["confidence"] for d in dets])) if dets else 0.0
            return (len(labels), mean_c, -abs(len(dets) - 8))

        best = max(frames, key=score)
        layout_frame = best["path"].name
        items = detections_to_items(best["dets"], best["size"][0], best["size"][1])

    if not items:
        progress(65, "No detections — using office layout fallback")
        items = fallback_office_items()

    actors = items_to_unreal_actors(items)
    progress(70, "{} objects → {} mesh parts".format(len(items), len(actors)))

    scene_doc = {
        "version": 3,
        "scene": "pipeline",
        "unit": "plotly_y_up",
        "unreal_unit_scale": 20.0,
        "source": {
            "kind": kind,
            "files": [str(p) for p in files],
            "layout_frame": layout_frame,
            "num_objects": len(items),
            "detections_by_class": counts,
            "pipeline": "DigitalTwinBuilder plugin (YOLO + furniture)",
        },
        "objects": items,
        "actors": actors,
    }
    scene_path = out / "unreal_scene.json"
    scene_path.write_text(json.dumps(scene_doc, indent=2), encoding="utf-8")
    (out / "digital_twin_objects.json").write_text(
        json.dumps({"objects": items, "detections_by_class": counts}, indent=2),
        encoding="utf-8",
    )
    progress(90, "Wrote {} ({} parts)".format(scene_path.name, len(actors)))
    progress(100, "Preprocess complete")
    print("SCENE_JSON:{}".format(scene_path), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        progress(100, "FAILED: {}".format(exc))
        raise
