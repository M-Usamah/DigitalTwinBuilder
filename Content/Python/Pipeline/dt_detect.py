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
KITCHEN_CLASSES = [
    "sink",
    "kitchen sink",
    "oven",
    "stove",
    "gas stove",
    "cooktop",
    "refrigerator",
    "fridge",
    "microwave",
    "toaster",
    "kettle",
    "dishwasher",
    "cabinet",
    "kitchen cabinet",
    "range hood",
    "extractor hood",
    "kitchen island",
    "chair",
    "stool",
    "plant",
    "potted plant",
    "vase",
    "faucet",
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
    "kitchen sink": "sink",
    "gas stove": "stove",
    "cooktop": "stove",
    "fridge": "refrigerator",
    "extractor hood": "range_hood",
    "range hood": "range_hood",
    "kitchen island": "island",
    "kitchen cabinet": "cabinet",
    "stool": "chair",
    "faucet": "sink",
}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".m4v", ".webm"}


def normalize_label(label: str) -> str:
    lab = label.strip().lower()
    return LABEL_ALIASES.get(lab, lab)


def bundled_weights_path() -> Path:
    return Path(__file__).resolve().parent / DEFAULT_DET_MODEL


def is_usable_checkpoint(path: str | Path) -> bool:
    """True only for a real PyTorch/Ultralytics weight file (not a Git LFS pointer)."""
    p = Path(path)
    try:
        if not p.is_file():
            return False
        size = p.stat().st_size
        if size < 1024 * 1024:
            return False
        with p.open("rb") as f:
            head = f.read(80)
        if head.startswith(b"version https://git-lfs.github.com"):
            return False
        return True
    except OSError:
        return False


def quarantine_lfs_pointer(path: Path) -> None:
    """Rename a Git LFS pointer so Ultralytics can download a real checkpoint."""
    if not path.is_file() or is_usable_checkpoint(path):
        return
    dest = path.with_name(path.name + ".lfs-pointer")
    try:
        if dest.exists():
            dest.unlink()
        path.rename(dest)
        print("Ignored Git LFS pointer (not real weights): {}".format(path.name), flush=True)
    except OSError:
        pass


def resolve_model_path(model_path: str | Path | None = None) -> str:
    """Return a loadable local .pt, or the Ultralytics name so it will be downloaded."""
    candidates = []
    if model_path:
        candidates.append(Path(model_path))
    candidates.append(bundled_weights_path())
    for p in candidates:
        if is_usable_checkpoint(p):
            return str(p)
        if p.is_file():
            quarantine_lfs_pointer(p)
    return DEFAULT_DET_MODEL


def _cache_downloaded_weights(model: YOLO) -> None:
    """Copy a downloaded Ultralytics checkpoint into the plugin Pipeline folder."""
    dest = bundled_weights_path()
    if is_usable_checkpoint(dest):
        return
    src = None
    for attr in ("ckpt_path", "weights"):
        val = getattr(model, attr, None)
        if val and is_usable_checkpoint(val):
            src = Path(str(val))
            break
    if src is None:
        from ultralytics.utils import WEIGHTS_DIR

        guessed = Path(WEIGHTS_DIR) / DEFAULT_DET_MODEL
        if is_usable_checkpoint(guessed):
            src = guessed
    if src is None:
        cwd = Path.cwd() / DEFAULT_DET_MODEL
        if is_usable_checkpoint(cwd):
            src = cwd
    if src is None:
        return
    try:
        import shutil

        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        print("Cached downloaded weights at {}".format(dest), flush=True)
    except OSError as exc:
        print("Could not cache weights ({}): {}".format(dest, exc), flush=True)


def load_detector(model_path: str | Path | None = None, scene: str = "auto") -> YOLO:
    path = resolve_model_path(model_path)
    clip_local = Path(__file__).resolve().parent / "weights" / "clip" / "ViT-B-32.pt"
    quarantine_lfs_pointer(clip_local)
    try:
        model = YOLO(str(path))
    except Exception as exc:
        print(
            "Local YOLO checkpoint failed ({}); downloading {} ...".format(exc, DEFAULT_DET_MODEL),
            flush=True,
        )
        model = YOLO(DEFAULT_DET_MODEL)
    _cache_downloaded_weights(model)
    if scene == "office":
        classes = OFFICE_CLASSES
    elif scene == "kitchen":
        classes = KITCHEN_CLASSES
    elif scene in ("auto", "any"):
        classes = list(dict.fromkeys(list(OFFICE_CLASSES) + list(BEDROOM_CLASSES) + list(KITCHEN_CLASSES)))
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
