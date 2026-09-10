"""Furniture parts for the Unreal twin (same layout as the Plotly office twin)."""

from __future__ import annotations

import math

C_DESK = (0.72, 0.55, 0.38)
C_LEG = (0.70, 0.72, 0.74)
C_CHAIR_BACK = (0.62, 0.64, 0.66)
C_CHAIR_SEAT = (0.12, 0.12, 0.14)
C_BASE = (0.10, 0.10, 0.12)
C_LAPTOP = (0.55, 0.55, 0.58)
C_MONITOR = (0.08, 0.08, 0.10)
C_KB = (0.15, 0.15, 0.18)
C_BOTTLE = (0.75, 0.85, 0.90)
C_BAG = (0.12, 0.18, 0.35)
C_PAPER = (0.95, 0.95, 0.95)


def _box_prim(xmin, xmax, ymin, ymax, zmin, zmax, rgb):
    return {
        "shape": "box",
        "center": [
            (xmin + xmax) * 0.5,
            (ymin + ymax) * 0.5,
            (zmin + zmax) * 0.5,
        ],
        "size": [xmax - xmin, ymax - ymin, zmax - zmin],
        "color": [float(rgb[0]), float(rgb[1]), float(rgb[2])],
    }


def _cyl_prim(cx, y0, cz, r, h, rgb):
    return {
        "shape": "cylinder",
        "center": [cx, y0 + h * 0.5, cz],
        "size": [r * 2.0, h, r * 2.0],
        "color": [float(rgb[0]), float(rgb[1]), float(rgb[2])],
    }


def local_furniture_prims(label: str) -> list[dict]:
    if label == "desk":
        top_h0, top_h1 = 4.0, 4.25
        parts = [
            _box_prim(-6.0, 6.0, top_h0, top_h1, -5.0, 5.5, C_DESK),
            _box_prim(-10.5, -5.5, top_h0, top_h1, -2.5, 4.0, C_DESK),
            _box_prim(5.5, 10.5, top_h0, top_h1, -2.5, 4.0, C_DESK),
            _box_prim(-4.0, 4.0, top_h0, top_h1, -7.5, -4.5, C_DESK),
            _box_prim(-2.5, -1.0, top_h1, top_h1 + 0.08, 0.5, 1.5, C_LEG),
            _box_prim(1.0, 2.5, top_h1, top_h1 + 0.08, 0.5, 1.5, C_LEG),
        ]
        for x, z in [(-8.5, -1.0), (8.5, -1.0), (-5.0, 4.0), (5.0, 4.0), (0.0, -6.0)]:
            parts.append(_box_prim(x - 0.2, x + 0.2, 0.0, top_h0, z - 0.2, z + 0.2, C_LEG))
        return parts
    if label == "chair":
        parts = [
            _box_prim(-2.0, 2.0, 2.4, 3.0, -2.0, 2.0, C_CHAIR_SEAT),
            _box_prim(-1.9, 1.9, 3.0, 7.0, -2.3, -1.4, C_CHAIR_BACK),
            _box_prim(-2.3, -1.7, 3.2, 4.0, -1.5, 1.5, C_BASE),
            _box_prim(1.7, 2.3, 3.2, 4.0, -1.5, 1.5, C_BASE),
            _cyl_prim(0.0, 1.2, 0.0, 0.35, 1.2, C_BASE),
            _cyl_prim(0.0, 0.35, 0.0, 0.7, 0.4, C_BASE),
        ]
        for deg in range(0, 360, 72):
            a = math.radians(deg)
            sx, sz = 2.4 * math.cos(a), 2.4 * math.sin(a)
            parts.append(_cyl_prim(sx * 0.55, 0.15, sz * 0.55, 0.22, 0.35, C_BASE))
            parts.append(_cyl_prim(sx, 0.0, sz, 0.35, 0.35, C_BASE))
        return parts
    if label == "monitor":
        return [
            _box_prim(-1.5, 1.5, 0.0, 0.2, -1.0, 1.0, C_BASE),
            _box_prim(-0.6, 0.6, 0.0, 1.2, -0.4, 0.4, C_BASE),
            _box_prim(-2.8, 2.8, 1.2, 5.2, -0.15, 0.15, C_MONITOR),
        ]
    if label == "laptop":
        return [
            _box_prim(-2.2, 2.2, 0.0, 0.25, -1.5, 1.5, C_LAPTOP),
            _box_prim(-2.1, 2.1, 0.25, 3.2, -1.6, -1.2, C_LAPTOP),
        ]
    if label == "keyboard":
        return [_box_prim(-2.2, 2.2, 0.0, 0.35, -0.9, 0.9, C_KB)]
    if label == "mouse":
        return [_box_prim(-0.5, 0.5, 0.0, 0.35, -0.8, 0.8, C_BASE)]
    if label == "bottle":
        return [_cyl_prim(0.0, 0.0, 0.0, 0.45, 2.4, C_BOTTLE)]
    if label == "backpack":
        return [_box_prim(-1.6, 1.6, 0.0, 4.5, -1.2, 1.2, C_BAG)]
    if label == "paper":
        return [_box_prim(-1.4, 1.4, 0.0, 0.05, -1.8, 1.8, C_PAPER)]
    if label == "table":
        return local_furniture_prims("desk")
    if label == "tv":
        return local_furniture_prims("monitor")
    return [_box_prim(-1.0, 1.0, 0.0, 2.0, -1.0, 1.0, (0.7, 0.7, 0.7))]


def _yaw_xz(x: float, z: float, deg: float) -> tuple[float, float]:
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    return float(ca * x - sa * z), float(sa * x + ca * z)


def items_to_unreal_actors(items: list[dict]) -> list[dict]:
    actors: list[dict] = []
    for it in items:
        lab = it["label"]
        yaw = float(it.get("yaw", 0.0))
        lift = float(it.get("lift", 0.0))
        ox, oz = float(it["X"]), float(it["Z"])
        prims = local_furniture_prims(lab)
        for i, p in enumerate(prims):
            cx, cy, cz = p["center"]
            wx, wz = _yaw_xz(cx, cz, yaw)
            actors.append(
                {
                    "id": "{}_p{:02d}".format(it["object_id"], i),
                    "group": it["object_id"],
                    "label": lab,
                    "shape": p["shape"],
                    "location": [wx + ox, cy + lift, wz + oz],
                    "yaw_deg": yaw,
                    "scale": p["size"],
                    "color": p["color"],
                    "show_label": False,
                }
            )
    return actors


def office_layout() -> list[dict]:
    desk_y = 4.25
    return [
        {"object_id": "desk_001", "label": "desk", "X": 0.0, "Z": 0.0, "yaw": 0.0},
        {"object_id": "chair_001", "label": "chair", "X": 0.0, "Z": -11.5, "yaw": 0.0},
        {"object_id": "chair_002", "label": "chair", "X": -11.0, "Z": 1.0, "yaw": 70.0},
        {"object_id": "chair_003", "label": "chair", "X": 11.0, "Z": 1.0, "yaw": -70.0},
        {
            "object_id": "monitor_001",
            "label": "monitor",
            "X": -1.0,
            "Z": 2.5,
            "yaw": 180.0,
            "lift": desk_y,
        },
        {
            "object_id": "keyboard_001",
            "label": "keyboard",
            "X": -1.0,
            "Z": 0.2,
            "yaw": 0.0,
            "lift": desk_y,
        },
        {
            "object_id": "laptop_001",
            "label": "laptop",
            "X": 5.5,
            "Z": 1.5,
            "yaw": -40.0,
            "lift": desk_y,
        },
        {
            "object_id": "mouse_001",
            "label": "mouse",
            "X": 2.5,
            "Z": 0.0,
            "yaw": 0.0,
            "lift": desk_y,
        },
        {
            "object_id": "bottle_001",
            "label": "bottle",
            "X": 7.0,
            "Z": -1.0,
            "yaw": 0.0,
            "lift": desk_y,
        },
        {
            "object_id": "paper_001",
            "label": "paper",
            "X": 4.5,
            "Z": -2.5,
            "yaw": 20.0,
            "lift": desk_y,
        },
        {"object_id": "backpack_001", "label": "backpack", "X": 8.5, "Z": -6.5, "yaw": 25.0},
    ]
