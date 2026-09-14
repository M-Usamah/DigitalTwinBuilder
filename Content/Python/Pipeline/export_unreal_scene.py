"""
Plugin-bundled Unreal export CLI (no project Content/python paths).

  py -3.12 export_unreal_scene.py --input <images|video|folder> --output <dir>

Prints PROGRESS: lines for the Unreal Output Log pump.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cv2
import numpy as np

import dt_detect as dtl
from dt_furniture import (
    items_to_unreal_actors,
    local_furniture_prims,
    office_layout,
    reception_layout,
    bedroom_layout,
)
import dt_layout
import dt_models
import dt_reconstruct
import dt_trellis
import dt_triposr


def progress(pct: int, msg: str) -> None:
    print("PROGRESS:{}|{}".format(max(0, min(100, int(pct))), msg), flush=True)


def _json_default(obj):
    if hasattr(obj, "item"):
        return obj.item()
    if hasattr(obj, "tolist"):
        return obj.tolist()
    return str(obj)


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


SURFACE = {
    "laptop",
    "monitor",
    "keyboard",
    "mouse",
    "bottle",
    "book",
    "phone",
    "cell phone",
    "paper",
    "cup",
}
CAPS = {
    "desk": 1,
    "table": 1,
    "chair": 8,
    "laptop": 4,
    "monitor": 4,
    "tv": 1,
    "keyboard": 1,
    "mouse": 1,
    "bottle": 2,
    "backpack": 1,
    "book": 2,
    "bed": 1,
    "lamp": 2,
    "nightstand": 2,
    "pillow": 4,
    "couch": 1,
    "curtain": 2,
    "mirror": 1,
    "plant": 2,
    "sink": 1,
    "stove": 1,
    "oven": 2,
    "refrigerator": 1,
    "cabinet": 6,
    "range_hood": 1,
    "island": 1,
    "toaster": 1,
    "kettle": 1,
    "vase": 2,
    "microwave": 1,
}
BEDROOM_LABELS = {
    "bed",
    "lamp",
    "nightstand",
    "pillow",
    "couch",
    "curtain",
    "mirror",
}
OFFICE_HINTS = (
    "desk",
    "table",
    "laptop",
    "keyboard",
    "mouse",
    "monitor",
    "backpack",
    "cell phone",
)
BEDROOM_HINTS = ("bed", "nightstand", "pillow")
KITCHEN_HINTS = (
    "sink",
    "stove",
    "oven",
    "refrigerator",
    "range_hood",
    "cabinet",
    "toaster",
    "kettle",
    "microwave",
    "dishwasher",
    "island",
)
OFFICE_KEEP = {
    "desk",
    "table",
    "chair",
    "laptop",
    "monitor",
    "keyboard",
    "mouse",
    "bottle",
    "backpack",
    "book",
    "cell phone",
    "plant",
    "paper",
    "cup",
}
BEDROOM_KEEP = {
    "bed",
    "chair",
    "lamp",
    "nightstand",
    "pillow",
    "couch",
    "curtain",
    "mirror",
    "plant",
    "bottle",
    "clock",
}
KITCHEN_KEEP = {
    "sink",
    "stove",
    "oven",
    "refrigerator",
    "cabinet",
    "range_hood",
    "island",
    "toaster",
    "kettle",
    "chair",
    "plant",
    "vase",
    "microwave",
    "table",
    "desk",
    "counter",
}


def detections_to_items(dets, img_w, img_h) -> list[dict]:
    dets = nms(dets)
    hosts = [d for d in dets if d["label"] in {"desk", "table"}]
    host_is_bed = False
    if not hosts:
        hosts = [d for d in dets if d["label"] == "bed"]
        host_is_bed = bool(hosts)
    desk = max(hosts, key=bbox_area) if hosts else None
    cleaned = []
    for d in dets:
        lab = d["label"]
        if lab in {"desk", "table"}:
            if desk is None or d is not desk:
                continue
            d = {**d, "label": "desk"}
        elif lab == "bed" and host_is_bed:
            if desk is None or d is not desk:
                continue
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

    is_bedroom = any(p["label"] == "bed" for p in kept)
    cleaned_kept = []
    for p in kept:
        lab = p["label"]
        # Glass walls in offices are often tagged as mirrors.
        if lab == "mirror" and not is_bedroom:
            continue
        if lab == "mirror" and p.get("y1", 1) <= 4:
            continue
        cleaned_kept.append(p)
    kept = cleaned_kept

    desks = [p for p in kept if p["label"] in {"desk", "bed"}]
    if not desks:
        cluster = [p for p in kept if p["label"] in {"sink", "stove", "oven", "cabinet", "island", "refrigerator"}]
        if cluster:
            ox = sum(p["X"] for p in cluster) / len(cluster)
            oz = sum(p["Z"] for p in cluster) / len(cluster)
            for p in kept:
                p["X"] -= ox
                p["Z"] -= oz
    else:
        ox, oz = desks[0]["X"], desks[0]["Z"]
        for p in kept:
            p["X"] -= ox
            p["Z"] -= oz

    host_xz = (desks[0]["X"], desks[0]["Z"]) if desks else (0.0, 0.0)
    host_label = desks[0]["label"] if desks else "desk"
    desk_h = prim_top(host_label) if desks else 0.0
    ns_h = prim_top("nightstand")

    chairs = [p for p in kept if p["label"] == "chair"]
    if False and chairs and host_label == "desk":
        _place_chairs_around_host(chairs, host_xz, radius=8.6)

    nightstands = [p for p in kept if p["label"] == "nightstand"]
    seq = {}
    items = []
    for p in kept:
        lab = p["label"]
        seq[lab] = seq.get(lab, 0) + 1
        if lab in SURFACE:
            if host_label == "desk":
                dist = math.hypot(p["X"] - host_xz[0], p["Z"] - host_xz[1])
                if dist > 5.4:
                    s = 5.4 / max(dist, 0.1)
                    p["X"] = host_xz[0] + (p["X"] - host_xz[0]) * s
                    p["Z"] = host_xz[1] + (p["Z"] - host_xz[1]) * s
                lift = desk_h
            elif on_desk_box(p, desk):
                lift = desk_h
            else:
                lift = 0.0
        elif lab == "pillow" and host_label == "bed":
            lift = max(desk_h - 0.8, 0.0)
        elif lab == "lamp" and nightstands:
            nearest = min(
                nightstands,
                key=lambda n: math.hypot(p["X"] - n["X"], p["Z"] - n["Z"]),
            )
            if math.hypot(p["X"] - nearest["X"], p["Z"] - nearest["Z"]) < 4.5:
                lift = ns_h
            else:
                lift = 0.0
        else:
            lift = 0.0
        yaw = 0.0
        if lab == "chair" and host_xz:
            dx = host_xz[0] - p["X"]
            dz = host_xz[1] - p["Z"]
            if abs(dx) + abs(dz) > 1e-4:
                yaw = math.degrees(math.atan2(-dx, dz))
        elif lab == "monitor":
            yaw = 180.0
        elif lab == "bed":
            yaw = 0.0
        items.append(
            {
                "object_id": "{}_{:03d}".format(lab, seq[lab]),
                "label": lab,
                "X": p["X"],
                "Z": p["Z"],
                "yaw": yaw,
                "lift": lift,
                "confidence": p["confidence"],
                "x1": p.get("x1"),
                "y1": p.get("y1"),
                "x2": p.get("x2"),
                "y2": p.get("y2"),
                "v": ((float(p.get("y1") or 0) + float(p.get("y2") or 0)) * 0.5) / max(img_h, 1),
            }
        )
    return items


def _place_chairs_around_host(chairs, host_xz, radius=8.6):
    """Keep detected chair angles, snap them onto a clean ring around the desk."""
    hx, hz = host_xz
    placed = []
    for ch in chairs:
        dx, dz = ch["X"] - hx, ch["Z"] - hz
        ang = math.atan2(dz, dx) if (abs(dx) + abs(dz) > 1e-4) else 0.0
        placed.append((ang, ch))
    placed.sort(key=lambda t: t[0])
    min_sep = math.radians(48.0)
    for i in range(1, len(placed)):
        prev, cur = placed[i - 1][0], placed[i][0]
        if cur - prev < min_sep:
            placed[i] = (prev + min_sep, placed[i][1])
    if len(placed) > 1:
        wrap = (placed[0][0] + 2.0 * math.pi) - placed[-1][0]
        if wrap < min_sep:
            placed[-1] = (placed[0][0] + 2.0 * math.pi - min_sep, placed[-1][1])
    for ang, ch in placed:
        ch["X"] = hx + radius * math.cos(ang)
        ch["Z"] = hz + radius * math.sin(ang)


def fallback_office_items() -> list[dict]:
    return office_layout()


LIVING_KEEP = {
    "couch",
    "chair",
    "table",
    "desk",
    "monitor",
    "lamp",
    "plant",
    "curtain",
}


def classify_scene(counts: dict, items: list[dict]) -> str:
    """Pick office vs bedroom vs living from detections, not from a hardcoded floor plan."""
    office_score = sum(int(counts.get(k, 0)) for k in OFFICE_HINTS)
    bedroom_score = sum(int(counts.get(k, 0)) for k in BEDROOM_HINTS)
    office_gear = sum(
        int(counts.get(k, 0))
        for k in ("laptop", "keyboard", "mouse", "monitor")
    )
    has_bed = int(counts.get("bed", 0)) >= 1 or any(it.get("label") == "bed" for it in items)
    has_desk = int(counts.get("desk", 0)) + int(counts.get("table", 0)) >= 1
    has_couch = int(counts.get("couch", 0)) + int(counts.get("sofa", 0)) >= 1
    kitchen_score = sum(int(counts.get(k, 0)) for k in KITCHEN_HINTS)
    kitchen_hit = (
        kitchen_score >= 2
        or int(counts.get("sink", 0))
        or int(counts.get("oven", 0))
        or int(counts.get("stove", 0))
        or int(counts.get("refrigerator", 0))
    )
    if kitchen_hit and not has_bed and office_gear < 2:
        return "kitchen"
    if has_bed and bedroom_score >= office_gear:
        return "bedroom"
    if office_gear >= 2 or (has_desk and office_score > bedroom_score):
        return "office"
    if has_couch and not has_bed and office_gear < 2:
        return "living"
    if has_desk or office_score >= bedroom_score:
        return "office"
    if has_bed:
        return "bedroom"
    return "office"


def filter_items_for_scene(items: list[dict], scene_kind: str) -> list[dict]:
    keep = OFFICE_KEEP
    if scene_kind == "bedroom":
        keep = BEDROOM_KEEP
    elif scene_kind == "living":
        keep = LIVING_KEEP
    elif scene_kind == "kitchen":
        keep = KITCHEN_KEEP
    return [it for it in items if it.get("label") in keep]


def _enrich_from_counts(items: list[dict], counts: dict) -> list[dict]:
    """Add obvious objects seen in other frames but missing from the layout frame."""
    labels = {it["label"] for it in items}
    has_desk = "desk" in labels
    has_bed = "bed" in labels
    desk_h = prim_top("desk") if has_desk else 0.0
    seq = {}
    for it in items:
        lab = it["label"]
        seq[lab] = seq.get(lab, 0) + 1

    def add(label, x, z, yaw=0.0, lift=0.0):
        seq[label] = seq.get(label, 0) + 1
        items.append(
            {
                "object_id": "{}_{:03d}".format(label, seq[label]),
                "label": label,
                "X": float(x),
                "Z": float(z),
                "yaw": float(yaw),
                "lift": float(lift),
                "confidence": 0.4,
            }
        )

    if has_desk and "monitor" not in labels and (counts.get("tv", 0) + counts.get("monitor", 0)):
        add("monitor", -1.4, 2.3, yaw=180.0, lift=desk_h)
    if has_desk and counts.get("laptop", 0) >= 2 and seq.get("laptop", 0) < 2:
        add("laptop", 4.6, 1.4, yaw=-25.0, lift=desk_h)
    if counts.get("plant", 0) and "plant" not in labels:
        add("plant", -10.5, 8.0)
    if has_desk and counts.get("backpack", 0) and "backpack" not in labels:
        add("backpack", 10.0, -8.5)
    return items


def arrange_office(items: list[dict], kind: str = "images", counts: dict | None = None) -> list[dict]:
    """Photos of the hex conference table vs the Skyarch reception video."""
    counts = counts or {}
    n_laptop = int(counts.get("laptop", 0))
    n_backpack = int(counts.get("backpack", 0))
    if kind == "video":
        return reception_layout()
    if n_laptop >= 2 or n_backpack >= 1:
        return office_layout()
    n_chairs = sum(1 for it in items if it["label"] == "chair")
    return office_layout() if n_chairs >= 3 else reception_layout()


def arrange_bedroom(items: list[dict]) -> list[dict]:
    return bedroom_layout()


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

    model_path = dtl.resolve_model_path(ROOT / "yolov8s-world.pt")
    if model_path == dtl.DEFAULT_DET_MODEL:
        progress(35, "Local YOLO weights missing/corrupt — downloading yolov8s-world.pt...")
    else:
        progress(35, "Loading YOLO-World...")
    try:
        yolo = dtl.load_detector(model_path, scene=args.scene or "auto")
    except Exception as exc:
        progress(36, "auto classes failed ({}); download + office vocab".format(exc))
        yolo = dtl.load_detector(dtl.DEFAULT_DET_MODEL, scene="office")

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

    scene_kind = classify_scene(counts, items)
    progress(64, "Scene from detections: {}".format(scene_kind))
    if scene_kind == "office" and frames:
        try:
            yolo_office = dtl.load_detector(model_path, scene="office")

            def office_frame_score(f):
                labs = [d["label"] for d in f["dets"]]
                n_office = sum(
                    1
                    for lab in labs
                    if lab in OFFICE_HINTS or lab in {"chair", "desk", "table"}
                )
                return (n_office, len(f["dets"]))

            best = max(frames, key=office_frame_score)
            frame = cv2.imread(str(best["path"]))
            if frame is not None:
                dets, plotted = dtl.detect_yolo(yolo_office, frame, conf=0.32, imgsz=960)
                cv2.imwrite(str(ann / best["path"].name), plotted)
                items = detections_to_items(dets, best["size"][0], best["size"][1])
                layout_frame = best["path"].name
                progress(66, "Office re-detect: {} objects".format(len(items)))
        except Exception as exc:
            progress(66, "Office re-detect skipped ({})".format(exc))

    items = filter_items_for_scene(items, scene_kind)
    if not items:
        progress(67, "No detections — schematic fallback")
        items = fallback_office_items()
    items = _enrich_from_counts(items, counts)
    items = filter_items_for_scene(items, scene_kind)

    recon = None
    layout_bgr = None
    if layout_frame:
        cand = images / layout_frame
        if cand.is_file():
            layout_bgr = cv2.imread(str(cand))

    mesh_backend = os.environ.get("DT_MESH_BACKEND", "prims").strip().lower()
    spawn_furniture = os.environ.get("DT_SPAWN_FURNITURE", "1").strip() not in {"0", "false", "no"}

    if mesh_backend in {"reconstruct", "scene", "depth"}:
        progress(70, "Reconstructing 3D from the uploaded media...")
        if layout_bgr is not None:
            try:
                recon = dt_reconstruct.reconstruct_frame(
                    layout_bgr, out / "scene_recon", progress=progress, stride=2
                )
            except Exception as exc:
                progress(78, "Scene reconstruct failed ({})".format(exc))
                recon = None
        if recon:
            progress(80, "Scene mesh from {} depth".format(recon.get("depth_source")))
            # Snap objects onto the reconstructed 3D.
            depth = recon["depth"]
            for it in items:
                x1, y1 = it.get("x1"), it.get("y1")
                x2, y2 = it.get("x2"), it.get("y2")
                if x1 is None or y1 is None or x2 is None or y2 is None:
                    continue
                u = 0.5 * (float(x1) + float(x2))
                v = 0.82 * float(y2) + 0.18 * float(y1)
                try:
                    px, py, pz = dt_reconstruct.unproject_pixel(u, v, depth, recon)
                    it["X"] = px
                    it["Z"] = pz
                    if it["label"] not in SURFACE and it["label"] not in {"pillow", "lamp"}:
                        it["lift"] = max(0.0, py)
                    elif it["label"] in SURFACE:
                        it["lift"] = max(it.get("lift", 0.0), py)
                except Exception:
                    pass
            # Desk / bed silhouette from the photo, not a canned hex or hotel plan.
            host = next((it for it in items if it["label"] in {"desk", "bed"}), None)
            if host is not None and layout_bgr is not None:
                hull = dt_reconstruct.desk_hull_xz(layout_bgr, host, recon, depth)
                if len(hull) >= 4:
                    hx, hz = float(host["X"]), float(host["Z"])
                    host["hull_xz"] = [[p[0] - hx, p[1] - hz] for p in hull]
                    host["style"] = "hull"
    elif mesh_backend in {"trellis2", "trellis.2"}:
        progress(70, "TRELLIS.2 image-to-3D (hosted microsoft/TRELLIS.2)...")
        items = dt_trellis.attach_trellis2_meshes(
            items,
            images,
            layout_frame,
            out,
            progress=progress,
        )
        if not any(it.get("mesh_source") == "trellis2" for it in items):
            progress(78, "TRELLIS.2 unavailable — schematic furniture")
    elif mesh_backend == "triposr" or os.environ.get("DT_USE_TRIPOSR", "").strip() == "1":
        items = dt_triposr.attach_triposr_meshes(
            items,
            images,
            layout_frame,
            out,
            progress=progress,
        )
    elif mesh_backend in {"prims", "layout"}:
        progress(70, "Schematic furniture from detections")

    desk_item = next((it for it in items if it.get("label") == "desk"), None)
    desk_style = "rect"
    if scene_kind == "office":
        desk_style = dt_layout.infer_desk_style(layout_bgr, desk_item, items, counts)
    if not any(it.get("mesh_source") == "trellis2" for it in items):
        items = dt_layout.compose_layout(items, scene_kind, counts, desk_style)
        progress(80, "Layout: {} ({} objects, desk={})".format(scene_kind, len(items), desk_style))

    for it in items:
        if it.get("mesh_source") == "trellis2" and it.get("mesh_path"):
            it["use_prims"] = False
        else:
            it["use_prims"] = True
            it.pop("mesh_path", None)

    actors = []
    if mesh_backend in {"reconstruct", "scene", "depth"} and recon and recon.get("obj_path"):
        actors.append(
            {
                "id": "scene_mesh",
                "group": "scene",
                "label": "scene",
                "shape": "imported",
                "mesh_path": recon["obj_path"],
                "location": [0.0, 0.0, 0.0],
                "lift": 0.0,
                "yaw_deg": 0.0,
                "scale": recon.get("size") or [20.0, 8.0, 20.0],
                "scale_mode": "fit_aabb",
                "coord": recon.get("coord") or "y_up",
                "color": [0.85, 0.85, 0.85],
                "show_label": False,
            }
        )
    if spawn_furniture or not recon:
        actors.extend(items_to_unreal_actors(items))
    n_imported = sum(1 for a in actors if a.get("shape") == "imported")
    progress(89, "{} objects → {} parts ({} imported)".format(len(items), len(actors), n_imported))

    scene_doc = {
        "version": 4,
        "scene": "pipeline",
        "unit": "plotly_y_up",
        "unreal_unit_scale": 20.0,
        "source": {
            "kind": kind,
            "files": [str(p) for p in files],
            "layout_frame": layout_frame,
            "num_objects": len(items),
            "detections_by_class": counts,
            "pipeline": "furniture layout ({})".format(scene_kind),
            "scene_kind": scene_kind,
            "mesh_backend": mesh_backend,
            "desk_style": desk_style,
            "depth_source": None if not recon else recon.get("depth_source"),
        },
        "reconstruction": None
        if not recon
        else {
            k: recon[k]
            for k in (
                "obj_path",
                "tex_path",
                "center",
                "size",
                "depth_source",
                "camera_eye",
                "coord",
                "width",
                "height",
                "relief",
            )
            if k in recon
        },
        "objects": items,
        "actors": actors,
    }
    scene_path = out / "unreal_scene.json"
    scene_path.write_text(json.dumps(scene_doc, indent=2, default=_json_default), encoding="utf-8")
    (out / "digital_twin_objects.json").write_text(
        json.dumps({"objects": items, "detections_by_class": counts}, indent=2),
        encoding="utf-8",
    )
    progress(90, "Wrote {} ({} parts)".format(scene_path.name, len(actors)))
    html_path = out / "digital_twin.html"
    try:
        import plot_unreal_scene as dt_plot

        dt_plot.plot_scene(scene_path, html_path)
        progress(96, "Preview HTML {}".format(html_path.name))
        print("HTML:{}".format(html_path), flush=True)
    except Exception as exc:
        progress(96, "HTML preview skipped ({})".format(exc))
    progress(100, "Preprocess complete")
    print("SCENE_JSON:{}".format(scene_path), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        progress(100, "FAILED: {}".format(exc))
        raise
