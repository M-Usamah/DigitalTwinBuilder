"""YOLO-World detection used by the plugin pipeline (no hloc / SfM)."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import cv2
import numpy as np
from ultralytics import YOLO

DEFAULT_DET_MODEL = "yolov8s-world.pt"

BEDROOM_CLASSES = [
    "bed",
    "chair",
    "armchair",
    "sofa",
    "couch",
    "lamp",
    "table lamp",
    "nightstand",
    "side table",
    "dining table",
    "coffee table",
    "pillow",
    "cushion",
    "curtain",
    "drapes",
    "mirror",
    "vase",
    "bottle",
    "potted plant",
    "tv",
    "television",
    "air conditioner",
    "clock",
    "painting",
]
OFFICE_CLASSES = [
    "desk",
    "table",
    "office chair",
    "chair",
    "laptop",
    "monitor",
    "keyboard",
    "mouse",
    "bottle",
    "backpack",
    "handbag",
    "book",
    "cell phone",
    "cup",
    "plant",
    "potted plant",
    "tv",
    "computer",
]
LABEL_ALIASES = {
    "armchair": "chair",
    "office chair": "chair",
    "sofa": "couch",
    "table lamp": "lamp",
    "side table": "nightstand",
    "dining table": "table",
    "coffee table": "table",
    "desk": "desk",
    "computer": "monitor",
    "cushion": "pillow",
    "drapes": "curtain",
    "television": "tv",
    "potted plant": "plant",
    "handbag": "backpack",
}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".m4v", ".webm"}


def normalize_label(label: str) -> str:
    lab = label.strip().lower()
    return LABEL_ALIASES.get(lab, lab)


def bundled_weights_path() -> Path:
    return Path(__file__).resolve().parent / DEFAULT_DET_MODEL


def resolve_model_path(model_path: str | Path | None = None) -> str:
    if model_path:
        p = Path(model_path)
        if p.is_file():
            return str(p)
        if str(model_path):
            return str(model_path)
    local = bundled_weights_path()
    if local.is_file():
        return str(local)
    return DEFAULT_DET_MODEL


def load_detector(model_path: str | Path | None = None, scene: str = "auto") -> YOLO:
    path = resolve_model_path(model_path)
    model = YOLO(str(path))
    if scene == "office":
        classes = OFFICE_CLASSES
    elif scene in ("auto", "any"):
        classes = list(dict.fromkeys(list(OFFICE_CLASSES) + list(BEDROOM_CLASSES)))
    else:
        classes = BEDROOM_CLASSES
    name = Path(path).name.lower()
    if "world" in name and hasattr(model, "set_classes"):
        try:
            model.set_classes(classes)
            print(
                "YOLO-World [{}] classes ({}): {}...".format(
                    scene, len(classes), ", ".join(classes[:8])
                ),
                flush=True,
            )
        except Exception as exc:
            print(
                "set_classes({}) failed ({}); using model default classes".format(scene, exc),
                flush=True,
            )
    return model


def extract_keyframes(video: Path, out_dir: Path, stride: int, max_frames: int) -> list[str]:
    if out_dir.exists():
        import shutil

        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError("Cannot open video: {}".format(video))
    names = []
    idx = saved = 0
    while saved < max_frames:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % max(stride, 1) == 0:
            name = "frame_{:04d}.jpg".format(saved)
            cv2.imwrite(str(out_dir / name), frame)
            names.append(name)
            saved += 1
        idx += 1
    cap.release()
    print("Extracted {} keyframes".format(len(names)), flush=True)
    return names


def detect_yolo(model: YOLO, frame_bgr: np.ndarray, conf: float, imgsz: int = 1280):
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    result = model.predict(
        source=rgb,
        conf=conf,
        imgsz=imgsz,
        iou=0.45,
        max_det=50,
        verbose=False,
    )[0]
    dets = []
    names = result.names or {}
    if result.boxes is None or len(result.boxes) == 0:
        return dets, result.plot()
    boxes = result.boxes.xyxy.cpu().numpy()
    scores = result.boxes.conf.cpu().numpy()
    classes = result.boxes.cls.cpu().numpy().astype(int)
    for box, score, cls_id in zip(boxes, scores, classes):
        x1, y1, x2, y2 = map(float, box)
        if (x2 - x1) < 12 or (y2 - y1) < 12:
            continue
        dets.append(
            {
                "label": normalize_label(names.get(int(cls_id), str(cls_id))),
                "confidence": float(score),
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
            }
        )
    return dets, result.plot()
