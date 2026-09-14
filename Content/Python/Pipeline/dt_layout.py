"""Turn detections into a readable furniture floor plan.

This is not a warped photo and not a single canned room. The object *set*
comes from YOLO; placement uses the photo's left/right/near/far plus
collision so the twin stays a real layout for office, bedroom, living, or
generic rooms.
"""

from __future__ import annotations

import math

import cv2
import numpy as np

from dt_furniture import BED_H, BED_LEN, BED_WID, HEX_R, local_furniture_prims


def _prim_top(label: str) -> float:
    prims = local_furniture_prims(label)
    return max(p["center"][1] + p["size"][1] * 0.5 for p in prims)


def _item(label, x, z, yaw=0.0, lift=0.0, style=None, **extra):
    it = {
        "label": label,
        "X": float(x),
        "Z": float(z),
        "yaw": float(yaw),
        "lift": float(lift),
        "use_prims": True,
    }
    if style:
        it["style"] = style
    it.update(extra)
    return it


def _finish(items: list[dict]) -> list[dict]:
    seq = {}
    out = []
    for it in items:
        lab = it["label"]
        seq[lab] = seq.get(lab, 0) + 1
        it = dict(it)
        it["object_id"] = "{}_{:03d}".format(lab, seq[lab])
        it.setdefault("use_prims", True)
        out.append(it)
    return out


def _count(items, *labels):
    return sum(1 for it in items if it.get("label") in labels)


def infer_desk_style(bgr, desk: dict | None, items: list[dict], counts: dict) -> str:
    """hex / l_desk / rect from silhouette + what sits around the table."""
    n_chair = _count(items, "chair") + int(counts.get("chair", 0) > 8)
    n_laptop = _count(items, "laptop") + int(counts.get("laptop", 0) >= 2)
    n_monitor = _count(items, "monitor") + int(counts.get("tv", 0) >= 2)
    n_pack = _count(items, "backpack") + int(counts.get("backpack", 0) >= 1)

    n_approx = 0
    solidity = 1.0
    if bgr is not None and desk is not None:
        n_approx, solidity = _desk_contour_stats(bgr, desk)

    if 5 <= n_approx <= 7 and solidity >= 0.88:
        return "hex"
    if solidity < 0.82 and n_approx >= 6:
        return "l_desk"
    # Conference table: people around a central desk, laptops, almost no monitors.
    if n_laptop >= 2 and n_chair >= 3 and n_monitor == 0:
        return "hex"
    if n_pack >= 1 and n_laptop >= 2 and n_chair >= 2:
        return "hex"
    # Reception / workstation: screens, few or no laptops.
    if n_monitor >= 2 and n_laptop == 0 and n_chair <= 4:
        return "l_desk"
    return "rect"


def _desk_contour_stats(bgr, det) -> tuple[int, float]:
    h, w = bgr.shape[:2]
    x1 = max(0, int(det.get("x1") or 0))
    y1 = max(0, int(det.get("y1") or 0))
    x2 = min(w, int(det.get("x2") or w))
    y2 = min(h, int(det.get("y2") or h))
    if x2 - x1 < 24 or y2 - y1 < 24:
        return 0, 1.0
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
        return 0, 1.0
    cnt = max(cnts, key=cv2.contourArea)
    area = float(cv2.contourArea(cnt))
    if area < 80:
        return 0, 1.0
    hull = cv2.convexHull(cnt)
    hull_a = float(cv2.contourArea(hull)) or 1.0
    peri = cv2.arcLength(cnt, True)
    approx = cv2.approxPolyDP(cnt, 0.03 * peri, True)
    return len(approx), float(area / hull_a)


def compose_layout(items: list[dict], scene_kind: str, counts: dict, desk_style: str) -> list[dict]:
    """Place furniture at YOLO positions. Only snap/lift; do not spawn a canned room."""
    items = [dict(it) for it in items]
    if scene_kind == "bedroom":
        return _finish(_from_dets_bedroom(items, counts))
    if scene_kind == "living":
        return _finish(_from_dets_living(items, counts))
    if scene_kind == "kitchen":
        return _finish(_from_dets_kitchen(items))
    return _finish(_from_dets_office(items, counts, desk_style))


def _copy_det(it, **over):
    lab = over.get("label", it["label"])
    return _item(
        lab,
        over.get("X", it.get("X", 0.0)),
        over.get("Z", it.get("Z", 0.0)),
        yaw=over.get("yaw", it.get("yaw", 0.0)),
        lift=over.get("lift", it.get("lift", 0.0)),
        style=over.get("style", it.get("style")),
        confidence=it.get("confidence"),
        x1=it.get("x1"),
        y1=it.get("y1"),
        x2=it.get("x2"),
        y2=it.get("y2"),
        v=it.get("v"),
    )


def _from_dets_office(items: list[dict], counts: dict, desk_style: str) -> list[dict]:
    desk_h = _prim_top("desk") if desk_style != "l_desk" else 4.05
    out = [_item("desk", 0.0, 0.0, style=desk_style)]
    for ch in [it for it in items if it["label"] == "chair"][:6]:
        x, z = float(ch.get("X", 0.0)), float(ch.get("Z", -8.0))
        r = math.hypot(x, z)
        need = 8.6 if desk_style == "hex" else 7.2
        if r < need:
            s = need / max(r, 0.2)
            x, z = x * s, z * s
        elif desk_style == "hex" and r > 0.2:
            s = need / r
            x, z = x * s, z * s
        out.append(_copy_det(ch, X=x, Z=z, yaw=math.degrees(math.atan2(-x, z)), lift=0.0))
    surface = ("laptop", "keyboard", "mouse", "monitor", "bottle", "cell phone", "paper", "cup")
    rmax = 6.4 if desk_style == "hex" else 5.6
    for it in items:
        lab = it["label"]
        if lab not in surface:
            continue
        if lab == "monitor" and desk_style == "hex":
            continue
        x, z = float(it.get("X", 0.0)), float(it.get("Z", 0.0))
        dist = math.hypot(x, z)
        if dist > rmax:
            s = rmax / max(dist, 0.1)
            x, z = x * s, z * s
        st = it.get("style")
        if lab == "keyboard" and desk_style == "hex":
            st = "rgb"
        yaw = 90.0 if desk_style == "l_desk" and lab == "monitor" else float(it.get("yaw") or (180.0 if lab == "monitor" else 0.0))
        out.append(_copy_det(it, X=x, Z=z, yaw=yaw, lift=desk_h, style=st, label=lab))
    for it in items:
        if it["label"] not in {"backpack", "plant"}:
            continue
        x, z = float(it.get("X", 10.0)), float(it.get("Z", -6.0))
        if math.hypot(x, z) < 9.5:
            s = 10.5 / max(math.hypot(x, z), 0.2)
            x, z = x * s, z * s
        out.append(_copy_det(it, X=x, Z=z, lift=0.0))
    return out


def _from_dets_bedroom(items: list[dict], counts: dict) -> list[dict]:
    bed = next((it for it in items if it["label"] == "bed"), None)
    out = [_item("bed", 0.0, 0.0)]
    for it in items:
        lab = it["label"]
        if lab == "bed":
            continue
        x, z = float(it.get("X", 0.0)), float(it.get("Z", 0.0))
        lift = float(it.get("lift") or 0.0)
        yaw = float(it.get("yaw") or 0.0)
        label = lab
        if lab == "pillow":
            lift = BED_H
            if abs(z) < 2:
                z = BED_LEN * 0.5 - 4.0
        elif lab == "lamp":
            ns = [n for n in items if n["label"] == "nightstand"]
            if ns:
                nearest = min(ns, key=lambda n: math.hypot(x - n["X"], z - n["Z"]))
                x, z = float(nearest["X"]), float(nearest["Z"])
            lift = 3.75
        elif lab == "chair":
            label = "accent_chair"
            if abs(x) + abs(z) > 1e-4:
                yaw = math.degrees(math.atan2(-x, z))
        elif lab == "table":
            label = "round_table"
        out.append(_copy_det(it, X=x, Z=z, yaw=yaw, lift=lift, label=label))
    return out


def _from_dets_kitchen(items: list[dict]) -> list[dict]:
    anchors = [
        it
        for it in items
        if it["label"] in {"sink", "stove", "oven", "cabinet", "refrigerator", "range_hood", "island", "toaster", "kettle"}
    ]
    out = _counters_from_points(anchors or items)
    top = 4.22
    for it in items:
        lab = it["label"]
        if lab in {"desk", "table", "counter"}:
            continue
        x, z = float(it.get("X", 0.0)), float(it.get("Z", 0.0))
        v = float(it.get("v") or 0.55)
        lift = 0.0
        yaw = float(it.get("yaw") or 0.0)
        if lab in {"sink", "stove", "toaster", "kettle", "vase", "bottle", "cup"}:
            lift = top
        elif lab == "plant":
            lift = top if v < 0.62 else 0.0
        elif lab == "range_hood":
            lift = 8.35
        elif lab == "cabinet":
            if v > 0.52:
                continue
            lift = 8.15
            if abs(x) > abs(z):
                yaw = 90.0 if x > 0 else -90.0
        elif lab == "oven":
            yaw = 90.0 if x > 0 else 0.0
        elif lab == "chair":
            lab = "guest_chair"
        out.append(_copy_det(it, X=x, Z=z, yaw=yaw, lift=lift, label=lab))
    return out


def _counters_from_points(pts: list[dict]) -> list[dict]:
    """Counter runs follow the cluster of detected kitchen objects, not a preset L."""
    if not pts:
        return [_item("counter", 0.0, 0.0, style="run_x")]
    xs = [float(p["X"]) for p in pts]
    zs = [float(p["Z"]) for p in pts]
    x0, x1, z0, z1 = min(xs), max(xs), min(zs), max(zs)
    out = []
    if x1 - x0 >= 3.5:
        med = sorted(zs)[len(zs) // 2]
        z_hi = [z for z in zs if z >= med]
        z_lo = [z for z in zs if z < med]
        z_wall = sum(z_hi) / len(z_hi) if len(z_hi) >= len(z_lo) else sum(z_lo) / max(len(z_lo), 1)
        out.append(_item("counter", (x0 + x1) * 0.5, z_wall, style="run_x"))
    if z1 - z0 >= 3.5:
        med = sorted(xs)[len(xs) // 2]
        x_hi = [x for x in xs if x >= med]
        x_lo = [x for x in xs if x < med]
        x_wall = sum(x_hi) / len(x_hi) if len(x_hi) >= len(x_lo) else sum(x_lo) / max(len(x_lo), 1)
        out.append(_item("counter", x_wall, (z0 + z1) * 0.5, style="run_z"))
    if not out:
        out.append(_item("counter", (x0 + x1) * 0.5, (z0 + z1) * 0.5, style="run_x"))
    return out


def _from_dets_living(items: list[dict], counts: dict) -> list[dict]:
    out = []
    for it in items:
        lab = it["label"]
        x, z = float(it.get("X", 0.0)), float(it.get("Z", 0.0))
        label = lab
        if lab == "table":
            label = "round_table"
        if lab == "chair":
            label = "accent_chair"
        if lab == "tv":
            label = "monitor"
        out.append(_copy_det(it, X=x, Z=z, label=label, lift=float(it.get("lift") or 0.0)))
    if not any(it["label"] == "couch" for it in out) and (counts.get("couch") or counts.get("sofa")):
        out.insert(0, _item("couch", 0.0, 6.0, yaw=180.0))
    return out or [_item("chair", 0.0, 0.0)]

