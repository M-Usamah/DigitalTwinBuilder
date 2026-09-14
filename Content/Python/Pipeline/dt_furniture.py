"""Furniture parts for the Unreal twin (same layout as the Plotly office twin)."""

from __future__ import annotations

import math

C_DESK = (0.72, 0.55, 0.36)
C_DESK_B = (0.64, 0.46, 0.28)
C_DESK_GREY = (0.42, 0.43, 0.45)
C_SLAT = (0.62, 0.42, 0.24)
C_LEG = (0.78, 0.79, 0.81)
C_LEG_GREY = (0.55, 0.56, 0.58)
C_CHAIR_BACK = (0.62, 0.64, 0.66)
C_CHAIR_SEAT = (0.08, 0.08, 0.09)
C_BASE = (0.10, 0.10, 0.12)
C_LAPTOP = (0.12, 0.12, 0.14)
C_MONITOR = (0.10, 0.10, 0.12)
C_SCREEN = (0.35, 0.55, 0.85)
C_KB = (0.15, 0.15, 0.18)
C_BOTTLE = (0.75, 0.85, 0.90)
C_BAG = (0.12, 0.18, 0.35)
C_BAG_RED = (0.28, 0.10, 0.12)
C_PAPER = (0.95, 0.95, 0.95)
C_BED = (0.78, 0.72, 0.64)
C_SHEET = (0.82, 0.76, 0.68)
C_RUNNER = (0.70, 0.64, 0.56)
C_HEAD = (0.62, 0.56, 0.50)
C_LAMP = (0.18, 0.14, 0.12)
C_LAMP_BASE = (0.55, 0.42, 0.28)
C_WOOD = (0.55, 0.40, 0.28)
C_COUCH = (0.35, 0.38, 0.42)
C_PILLOW = (0.80, 0.74, 0.66)
C_NIGHT = (0.08, 0.08, 0.09)
C_ACCENT = (0.93, 0.88, 0.80)
C_ACCENT_SIDE = (0.10, 0.09, 0.08)
C_VANITY = (0.10, 0.09, 0.08)
C_GLOW = (0.95, 0.78, 0.45)
C_CAB = (0.91, 0.92, 0.93)
C_COUNTER = (0.97, 0.97, 0.98)
C_STEEL = (0.70, 0.72, 0.74)
C_HOB = (0.16, 0.16, 0.17)
C_OVEN = (0.10, 0.10, 0.11)

BED_LEN = 24.0
BED_WID = 17.0
BED_H = 3.2
HEAD_H = 9.2
HEX_R = 9.2

SIZE_HINT = {
    "desk": [18.4, 4.22, 18.4],
    "table": [18.4, 4.22, 18.4],
    "chair": [4.4, 7.0, 4.4],
    "guest_chair": [3.6, 5.5, 3.8],
    "bed": [17.0, 9.2, 24.0],
    "lamp": [3.7, 5.5, 3.7],
    "nightstand": [3.6, 4.0, 3.6],
    "pillow": [3.6, 1.2, 3.2],
    "accent_chair": [5.2, 6.4, 5.0],
    "vanity_chair": [4.4, 5.4, 4.2],
    "vanity": [8.5, 3.4, 3.2],
    "round_table": [3.6, 3.5, 3.6],
    "clock": [2.4, 2.4, 0.18],
    "couch": [13.8, 5.1, 5.7],
    "curtain": [5.8, 13.9, 0.5],
    "mirror": [3.4, 3.4, 0.18],
    "monitor": [4.6, 4.6, 1.4],
    "laptop": [4.3, 2.9, 3.0],
    "keyboard": [4.3, 0.28, 1.7],
    "mouse": [0.9, 0.34, 1.4],
    "bottle": [0.8, 2.3, 0.8],
    "backpack": [2.9, 4.2, 2.3],
    "plant": [2.6, 5.8, 2.6],
    "paper": [2.7, 0.05, 3.4],
    "book": [2.2, 0.28, 3.0],
    "cell phone": [1.1, 0.12, 2.1],
    "counter": [16.0, 4.2, 3.4],
    "sink": [4.2, 1.2, 2.4],
    "stove": [5.6, 0.35, 3.0],
    "oven": [3.6, 10.5, 3.4],
    "range_hood": [5.2, 3.2, 2.6],
    "refrigerator": [4.2, 12.5, 3.6],
    "cabinet": [6.0, 4.2, 1.8],
    "island": [10.0, 4.2, 5.2],
    "toaster": [2.2, 1.6, 1.4],
    "kettle": [1.5, 2.0, 1.5],
}


def _yaw_xz(x: float, z: float, deg: float) -> tuple[float, float]:
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    return float(ca * x - sa * z), float(sa * x + ca * z)


def _box_prim(xmin, xmax, ymin, ymax, zmin, zmax, rgb, yaw=0.0):
    return {
        "shape": "box",
        "center": [
            (xmin + xmax) * 0.5,
            (ymin + ymax) * 0.5,
            (zmin + zmax) * 0.5,
        ],
        "size": [xmax - xmin, ymax - ymin, zmax - zmin],
        "color": [float(rgb[0]), float(rgb[1]), float(rgb[2])],
        "yaw": float(yaw),
    }


def _cyl_prim(cx, y0, cz, r, h, rgb):
    return {
        "shape": "cylinder",
        "center": [cx, y0 + h * 0.5, cz],
        "size": [r * 2.0, h, r * 2.0],
        "color": [float(rgb[0]), float(rgb[1]), float(rgb[2])],
    }


def _rect_desk():
    top_h0, top_h1 = 4.0, 4.25
    parts = [
        _box_prim(-7.2, 7.2, top_h0, top_h1, -4.2, 4.2, C_DESK),
        _box_prim(-7.0, -6.6, 0.0, top_h0, -4.0, -3.6, C_LEG),
        _box_prim(6.6, 7.0, 0.0, top_h0, -4.0, -3.6, C_LEG),
        _box_prim(-7.0, -6.6, 0.0, top_h0, 3.6, 4.0, C_LEG),
        _box_prim(6.6, 7.0, 0.0, top_h0, 3.6, 4.0, C_LEG),
    ]
    return parts


def _hex_desk():
    """Regular hexagon table: 6 slabs whose outer edges are the flats."""
    r = HEX_R
    side = r
    apothem = r * math.sqrt(3.0) * 0.5
    top_h0, top_h1 = 4.0, 4.22
    cy = (top_h0 + top_h1) * 0.5
    thick = top_h1 - top_h0
    parts = []
    for k in range(6):
        deg = k * 60.0
        cx, cz = _yaw_xz(0.0, apothem * 0.5, deg)
        wood = C_DESK if k % 2 == 0 else C_DESK_B
        parts.append(
            {
                "shape": "box",
                "center": [cx, cy, cz],
                "size": [side, thick, apothem],
                "color": [float(wood[0]), float(wood[1]), float(wood[2])],
                "yaw": deg,
            }
        )
    # Square silver legs at the six vertices (slightly inset).
    for k in range(6):
        deg = 30.0 + k * 60.0
        lx = 0.78 * r * math.cos(math.radians(deg))
        lz = 0.78 * r * math.sin(math.radians(deg))
        parts.append(_box_prim(lx - 0.22, lx + 0.22, 0.0, top_h0, lz - 0.22, lz + 0.22, C_LEG))
    parts.append(_box_prim(-2.15, -0.65, top_h1, top_h1 + 0.05, -0.55, 0.85, C_LEG))
    parts.append(_box_prim(0.65, 2.15, top_h1, top_h1 + 0.05, -0.55, 0.85, C_LEG))
    return parts


def _l_desk():
    """Solid grey L-shaped reception desk (Skyarch video) with wood slats."""
    top = 4.05
    parts = [
        # Return against the back wall (binders live here).
        _box_prim(-6.8, 3.4, 0.0, top, 2.2, 5.5, C_DESK_GREY),
        # Main counter toward the visitor side.
        _box_prim(3.4, 8.4, 0.0, top, -3.6, 5.5, C_DESK_GREY),
        # Wood slats on the visitor-facing (+X) side + warm underglow.
        _box_prim(8.4, 8.55, 0.18, top - 0.08, -3.5, 5.4, C_SLAT),
    ]
    for i in range(14):
        z0 = -3.45 + i * 0.62
        parts.append(_box_prim(8.42, 8.62, 0.22, top - 0.12, z0, z0 + 0.38, C_SLAT))
    parts.append(_box_prim(8.35, 8.58, 0.04, 0.16, -3.5, 5.4, C_GLOW))
    # Binders on the return.
    for i, col in enumerate(
        ((0.12, 0.12, 0.14), (0.18, 0.42, 0.22), (0.12, 0.12, 0.14), (0.12, 0.12, 0.14), (0.12, 0.12, 0.14))
    ):
        x0 = -4.6 + i * 0.72
        parts.append(_box_prim(x0, x0 + 0.58, top, top + 2.15, 4.35, 5.25, col))
    # Cards / tiny succulent on the main counter.
    parts.append(_box_prim(5.1, 6.3, top, top + 0.04, 0.4, 1.3, C_PAPER))
    parts.append(_cyl_prim(6.9, top, -0.2, 0.35, 0.45, (0.18, 0.42, 0.22)))
    parts.append(_cyl_prim(6.9, top, -0.2, 0.28, 0.22, (0.55, 0.55, 0.52)))
    return parts


def _point_in_poly(x: float, z: float, poly: list) -> bool:
    n = len(poly)
    inside = False
    j = n - 1
    for i in range(n):
        xi, zi = poly[i][0], poly[i][1]
        xj, zj = poly[j][0], poly[j][1]
        if (zi > z) != (zj > z) and x < (xj - xi) * (z - zi) / (zj - zi + 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def _hull_desk(hull_xz: list) -> list[dict]:
    """Desk top extruded from the photographed table silhouette."""
    if not hull_xz or len(hull_xz) < 3:
        return _rect_desk()
    xs = [p[0] for p in hull_xz]
    zs = [p[1] for p in hull_xz]
    top_h0, top_h1 = 4.0, 4.22
    parts = []
    step = 0.85
    x0, x1 = min(xs), max(xs)
    z0, z1 = min(zs), max(zs)
    x = x0
    while x < x1:
        z = z0
        while z < z1:
            cx, cz = x + step * 0.5, z + step * 0.5
            if _point_in_poly(cx, cz, hull_xz):
                parts.append(_box_prim(x, min(x + step, x1), top_h0, top_h1, z, min(z + step, z1), C_DESK))
            z += step
        x += step
    if not parts:
        return _rect_desk()
    for px, pz in hull_xz:
        parts.append(_box_prim(px - 0.2, px + 0.2, 0.0, top_h0, pz - 0.2, pz + 0.2, C_LEG))
    return parts


def local_furniture_prims(label: str, style: str | None = None, hull=None) -> list[dict]:
    if label in {"desk", "table"}:
        if style == "hull" and hull:
            return _hull_desk(hull)
        if style == "hex":
            return _hex_desk()
        if style == "l_desk":
            return _l_desk()
        return _rect_desk()
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
            _box_prim(-1.3, 1.3, 0.0, 0.16, -0.85, 0.85, C_LEG),
            _box_prim(-0.22, 0.22, 0.16, 1.35, -0.22, 0.22, C_LEG),
            _box_prim(-2.25, 2.25, 1.35, 4.55, -0.12, 0.12, C_MONITOR),
            _box_prim(-2.05, 2.05, 1.5, 4.35, -0.14, -0.08, C_SCREEN),
        ]
    if label == "laptop":
        if style == "closed":
            return [_box_prim(-2.0, 2.0, 0.0, 0.22, -1.35, 1.35, C_LAPTOP)]
        return [
            _box_prim(-2.2, 2.2, 0.0, 0.22, -1.5, 1.5, C_LAPTOP),
            _box_prim(-2.1, 2.1, 0.22, 3.15, -1.62, -1.22, C_LAPTOP),
            _box_prim(-1.9, 1.9, 0.45, 2.95, -1.60, -1.38, C_SCREEN),
        ]
    if label == "guest_chair":
        parts = [
            _box_prim(-1.65, 1.65, 2.55, 2.95, -1.55, 1.55, C_CHAIR_SEAT),
            _box_prim(-1.65, 1.65, 2.95, 5.35, -1.75, -1.25, C_CHAIR_SEAT),
        ]
        for sx, sz in ((-1.35, -1.25), (1.35, -1.25), (-1.35, 1.25), (1.35, 1.25)):
            parts.append(_cyl_prim(sx, 0.0, sz, 0.11, 2.55, C_LEG))
        return parts
    if label == "keyboard":
        if style == "rgb":
            return [
                _box_prim(-2.0, 2.0, 0.0, 0.22, -0.75, 0.75, C_KB),
                _box_prim(-1.8, -0.6, 0.22, 0.32, -0.55, 0.55, (0.95, 0.28, 0.18)),
                _box_prim(-0.6, 0.6, 0.22, 0.32, -0.55, 0.55, (0.22, 0.82, 0.32)),
                _box_prim(0.6, 1.8, 0.22, 0.32, -0.55, 0.55, (0.22, 0.42, 0.95)),
            ]
        return [_box_prim(-2.0, 2.0, 0.0, 0.22, -0.75, 0.75, C_KB)]
    if label == "mouse":
        return [_box_prim(-0.5, 0.5, 0.0, 0.35, -0.8, 0.8, C_BASE)]
    if label == "bottle":
        return [_cyl_prim(0.0, 0.0, 0.0, 0.45, 2.4, C_BOTTLE)]
    if label == "backpack":
        col = C_BAG_RED if style == "red" else C_BAG
        return [_box_prim(-1.6, 1.6, 0.0, 4.5, -1.2, 1.2, col)]
    if label == "paper":
        return [_box_prim(-1.4, 1.4, 0.0, 0.05, -1.8, 1.8, C_PAPER)]
    if label == "cup":
        return [_cyl_prim(0.0, 0.0, 0.0, 0.45, 1.1, (0.82, 0.82, 0.84))]
    if label == "cell phone":
        return [_box_prim(-0.55, 0.55, 0.0, 0.12, -1.05, 1.05, (0.12, 0.12, 0.14))]
    if label == "table":
        return local_furniture_prims("desk")
    if label == "tv":
        return local_furniture_prims("monitor")
    if label == "bed":
        hw, hl = BED_WID * 0.5, BED_LEN * 0.5
        return [
            _box_prim(-hw, hw, 0.0, 1.5, -hl, hl - 0.6, C_BED),
            _box_prim(-hw + 0.25, hw - 0.25, 1.5, BED_H, -hl + 0.35, hl - 1.4, C_SHEET),
            _box_prim(-hw + 0.35, hw - 0.35, BED_H, BED_H + 0.22, -hl + 0.4, -hl + 7.2, C_RUNNER),
            _box_prim(-hw - 0.35, hw + 0.35, 0.0, HEAD_H, hl - 1.15, hl + 0.55, C_HEAD),
            _box_prim(-hw - 0.35, -hw + 1.35, HEAD_H * 0.28, HEAD_H, hl - 4.8, hl - 1.15, C_HEAD),
            _box_prim(hw - 1.35, hw + 0.35, HEAD_H * 0.28, HEAD_H, hl - 4.8, hl - 1.15, C_HEAD),
        ]
    if label == "lamp":
        return [
            _cyl_prim(0.0, 0.0, 0.0, 0.85, 0.22, C_LAMP_BASE),
            _cyl_prim(0.0, 0.22, 0.0, 0.18, 2.4, C_LAMP_BASE),
            _cyl_prim(0.0, 2.55, 0.0, 1.45, 0.12, C_LAMP),
            _cyl_prim(0.0, 2.67, 0.0, 1.35, 2.05, C_LAMP),
            _cyl_prim(0.0, 4.72, 0.0, 0.95, 0.35, C_LAMP),
        ]
    if label == "nightstand":
        return [
            _box_prim(-1.7, 1.7, 0.12, 3.55, -1.55, 1.55, C_NIGHT),
            _box_prim(-1.75, 1.75, 3.55, 3.75, -1.6, 1.6, C_NIGHT),
            _box_prim(-0.25, 0.25, 2.2, 2.55, 1.45, 1.62, (0.72, 0.62, 0.38)),
            _cyl_prim(-1.45, 0.0, -1.3, 0.12, 0.12, (0.72, 0.62, 0.38)),
            _cyl_prim(1.45, 0.0, -1.3, 0.12, 0.12, (0.72, 0.62, 0.38)),
            _cyl_prim(-1.45, 0.0, 1.3, 0.12, 0.12, (0.72, 0.62, 0.38)),
            _cyl_prim(1.45, 0.0, 1.3, 0.12, 0.12, (0.72, 0.62, 0.38)),
        ]
    if label == "pillow":
        return [_box_prim(-1.7, 1.7, 0.0, 1.15, -1.45, 1.45, C_PILLOW)]
    if label == "accent_chair":
        return [
            _box_prim(-2.15, 2.15, 2.15, 2.95, -2.05, 2.05, C_ACCENT),
            _box_prim(-2.15, 2.15, 2.95, 6.15, -2.25, -1.35, C_ACCENT),
            _box_prim(-2.45, -1.95, 0.0, 6.2, -2.2, 2.15, C_ACCENT_SIDE),
            _box_prim(1.95, 2.45, 0.0, 6.2, -2.2, 2.15, C_ACCENT_SIDE),
        ]
    if label == "vanity_chair":
        gold = (0.72, 0.62, 0.38)
        return [
            _cyl_prim(0.0, 0.0, 0.0, 1.45, 0.12, gold),
            _cyl_prim(0.0, 0.12, 0.0, 0.12, 2.05, gold),
            _box_prim(-1.7, 1.7, 2.15, 2.75, -1.7, 1.7, C_ACCENT),
            _box_prim(-1.7, 1.7, 2.75, 5.15, -1.95, -1.25, C_ACCENT),
        ]
    if label == "vanity":
        gold = (0.72, 0.62, 0.38)
        return [
            _box_prim(-3.4, 3.4, 3.05, 3.35, -1.25, 1.25, C_VANITY),
            _box_prim(-3.2, -2.6, 0.0, 3.05, -1.05, 1.05, C_VANITY),
            _box_prim(2.6, 3.2, 0.0, 3.05, -1.05, 1.05, C_VANITY),
            _cyl_prim(-3.05, 0.0, -1.05, 0.08, 0.08, gold),
            _cyl_prim(3.05, 0.0, -1.05, 0.08, 0.08, gold),
            _cyl_prim(-3.05, 0.0, 1.05, 0.08, 0.08, gold),
            _cyl_prim(3.05, 0.0, 1.05, 0.08, 0.08, gold),
        ]
    if label == "round_table":
        return [
            _cyl_prim(0.0, 0.0, 0.0, 1.4, 0.4, C_NIGHT),
            _cyl_prim(0.0, 0.4, 0.0, 0.45, 3.0, C_NIGHT),
            _cyl_prim(0.0, 3.4, 0.0, 2.2, 0.25, C_NIGHT),
        ]
    if label == "clock":
        return [
            _cyl_prim(0.0, 0.0, 0.0, 1.15, 0.16, (0.06, 0.06, 0.07)),
            _cyl_prim(0.0, 0.16, 0.0, 0.95, 0.04, (0.18, 0.16, 0.14)),
        ]
    if label in {"couch", "sofa"}:
        return [
            _box_prim(-7.0, 7.0, 0.0, 2.4, -3.0, 3.0, C_COUCH),
            _box_prim(-7.0, 7.0, 2.4, 5.2, 2.0, 3.0, C_COUCH),
            _box_prim(-7.0, -5.8, 2.4, 4.4, -2.5, 2.0, C_COUCH),
            _box_prim(5.8, 7.0, 2.4, 4.4, -2.5, 2.0, C_COUCH),
        ]
    if label == "curtain":
        return [_box_prim(-3.0, 3.0, 0.0, 14.0, -0.25, 0.25, (0.55, 0.52, 0.48))]
    if label == "mirror":
        return [
            _box_prim(-1.7, 1.7, 0.0, 3.4, -0.10, 0.10, (0.72, 0.62, 0.38)),
            _box_prim(-1.5, 1.5, 0.18, 3.22, -0.12, 0.04, (0.78, 0.84, 0.88)),
        ]
    if label in {"plant", "potted plant"}:
        return [
            _cyl_prim(0.0, 0.0, 0.0, 0.9, 1.4, C_WOOD),
            _cyl_prim(0.0, 1.4, 0.0, 1.4, 4.5, (0.22, 0.48, 0.28)),
        ]
    if label == "vase":
        return [
            _cyl_prim(0.0, 0.0, 0.0, 0.85, 1.8, (0.94, 0.94, 0.95)),
            _cyl_prim(0.0, 1.6, 0.0, 1.15, 2.4, (0.78, 0.82, 0.72)),
        ]
    if label == "counter":
        along_z = style == "run_z"
        length = 16.0 if not along_z else 12.5
        depth = 3.35
        hx, hz = (length * 0.5, depth * 0.5) if not along_z else (depth * 0.5, length * 0.5)
        parts = [
            _box_prim(-hx, hx, 0.0, 4.0, -hz, hz, C_CAB),
            _box_prim(-hx - 0.08, hx + 0.08, 4.0, 4.22, -hz - 0.12, hz + 0.12, C_COUNTER),
        ]
        # Door splits so the top-down reads as cabinets, not one slab.
        n = 5 if not along_z else 4
        for i in range(1, n):
            t = i / n
            if along_z:
                z = -hz + t * length
                parts.append(_box_prim(-hx, hx, 0.12, 3.92, z - 0.04, z + 0.04, C_STEEL))
            else:
                x = -hx + t * length
                parts.append(_box_prim(x - 0.04, x + 0.04, 0.12, 3.92, -hz, hz, C_STEEL))
        return parts
    if label == "sink":
        return [
            _box_prim(-1.9, 1.9, 0.0, 0.12, -1.15, 1.15, C_STEEL),
            _box_prim(-1.55, 1.55, -0.55, 0.0, -0.85, 0.85, (0.45, 0.47, 0.48)),
            _cyl_prim(0.0, 0.12, -0.15, 0.12, 1.55, C_STEEL),
            _box_prim(-0.55, 0.85, 1.55, 1.72, -0.18, 0.18, C_STEEL),
        ]
    if label == "stove":
        parts = [_box_prim(-2.6, 2.6, 0.0, 0.18, -1.45, 1.45, C_HOB)]
        for dx in (-1.15, 1.15):
            for dz in (-0.55, 0.55):
                parts.append(_cyl_prim(dx, 0.18, dz, 0.55, 0.08, (0.28, 0.28, 0.30)))
        return parts
    if label == "oven":
        return [
            _box_prim(-1.7, 1.7, 0.0, 10.4, -1.55, 1.55, C_CAB),
            _box_prim(-1.35, 1.35, 1.4, 5.1, -1.62, -1.42, C_OVEN),
            _box_prim(-1.35, 1.35, 5.5, 9.3, -1.62, -1.42, C_OVEN),
            _box_prim(-0.55, 0.55, 9.45, 9.85, -1.62, -1.48, C_STEEL),
        ]
    if label == "range_hood":
        return [
            _box_prim(-2.4, 2.4, 0.0, 1.15, -1.15, 1.15, C_STEEL),
            _box_prim(-0.85, 0.85, 1.15, 3.4, -0.55, 0.55, C_STEEL),
        ]
    if label == "refrigerator":
        return [
            _box_prim(-1.9, 1.9, 0.0, 12.4, -1.6, 1.6, C_CAB),
            _box_prim(-1.7, 1.7, 0.35, 7.4, -1.68, -1.52, C_STEEL),
            _box_prim(-1.7, 1.7, 7.7, 12.05, -1.68, -1.52, C_STEEL),
        ]
    if label == "cabinet":
        return [
            _box_prim(-2.8, 2.8, 0.0, 4.1, -0.85, 0.85, C_CAB),
            _box_prim(-0.08, 0.08, 0.25, 3.85, -0.85, 0.85, C_STEEL),
        ]
    if label == "island":
        return [
            _box_prim(-4.8, 4.8, 0.0, 4.0, -2.3, 2.3, C_CAB),
            _box_prim(-5.0, 5.0, 4.0, 4.22, -2.45, 2.45, C_COUNTER),
        ]
    if label == "toaster":
        return [_box_prim(-1.05, 1.05, 0.0, 1.45, -0.65, 0.65, (0.93, 0.91, 0.86))]
    if label == "kettle":
        return [_cyl_prim(0.0, 0.0, 0.0, 0.7, 1.85, (0.93, 0.91, 0.86))]
    return [_box_prim(-1.0, 1.0, 0.0, 2.0, -1.0, 1.0, (0.7, 0.7, 0.7))]


def items_to_unreal_actors(items: list[dict]) -> list[dict]:
    actors: list[dict] = []
    for it in items:
        lab = it["label"]
        yaw = float(it.get("yaw", 0.0))
        lift = float(it.get("lift", 0.0))
        ox, oz = float(it["X"]), float(it["Z"])
        mesh_path = None if it.get("use_prims") else it.get("mesh_path")
        if mesh_path:
            hint = SIZE_HINT.get(lab, [3.0, 3.0, 3.0])
            color = it.get("color")
            actors.append(
                {
                    "id": it["object_id"],
                    "group": it["object_id"],
                    "label": lab,
                    "shape": "imported",
                    "mesh_path": mesh_path,
                    "location": [ox, lift, oz],
                    "lift": lift,
                    "yaw_deg": yaw,
                    "scale": list(hint),
                    "color": color,
                    "show_label": False,
                }
            )
            continue
        prims = local_furniture_prims(lab, style=it.get("style"), hull=it.get("hull_xz"))
        for i, p in enumerate(prims):
            cx, cy, cz = p["center"]
            prim_yaw = float(p.get("yaw", 0.0))
            wx, wz = _yaw_xz(cx, cz, yaw)
            actors.append(
                {
                    "id": "{}_p{:02d}".format(it["object_id"], i),
                    "group": it["object_id"],
                    "label": lab,
                    "shape": p["shape"],
                    "location": [wx + ox, cy + lift, wz + oz],
                    "yaw_deg": yaw + prim_yaw,
                    "scale": p["size"],
                    "color": p["color"],
                    "show_label": False,
                }
            )
    return actors


def office_layout() -> list[dict]:
    """Hex conference table from the Helpdesk photos: 3 chairs on three flats."""
    desk_y = 4.22
    apothem = HEX_R * math.sqrt(3.0) * 0.5
    chair_r = apothem + 4.15
    items = [
        {"object_id": "desk_001", "label": "desk", "X": 0.0, "Z": 0.0, "yaw": 0.0, "style": "hex"},
    ]
    # Flats whose outward normals are world 90/210/330° sit at _yaw_xz yaws 0/120/240.
    for i, yaw in enumerate((0.0, 120.0, 240.0)):
        x, z = _yaw_xz(0.0, chair_r, yaw)
        items.append(
            {
                "object_id": "chair_{:03d}".format(i + 1),
                "label": "chair",
                "X": x,
                "Z": z,
                "yaw": math.degrees(math.atan2(x, -z)),
                "lift": 0.0,
            }
        )
    items.extend(
        [
            {"object_id": "laptop_001", "label": "laptop", "X": -4.2, "Z": 1.1, "yaw": 18.0, "lift": desk_y, "style": "closed"},
            {"object_id": "laptop_002", "label": "laptop", "X": -0.2, "Z": 2.0, "yaw": -8.0, "lift": desk_y},
            {"object_id": "keyboard_001", "label": "keyboard", "X": -1.6, "Z": -0.35, "yaw": 10.0, "lift": desk_y, "style": "rgb"},
            {"object_id": "mouse_001", "label": "mouse", "X": 1.15, "Z": -0.15, "yaw": 8.0, "lift": desk_y},
            {"object_id": "mouse_002", "label": "mouse", "X": 2.05, "Z": 0.55, "yaw": -12.0, "lift": desk_y},
            {"object_id": "phone_001", "label": "cell phone", "X": 0.35, "Z": 0.15, "yaw": 22.0, "lift": desk_y},
            {"object_id": "bottle_001", "label": "bottle", "X": 4.4, "Z": -2.0, "yaw": 0.0, "lift": desk_y},
            {"object_id": "paper_001", "label": "paper", "X": 3.6, "Z": 3.1, "yaw": -18.0, "lift": desk_y},
            {"object_id": "backpack_001", "label": "backpack", "X": 7.6, "Z": -6.8, "yaw": 25.0},
            {"object_id": "backpack_002", "label": "backpack", "X": -6.6, "Z": -6.4, "yaw": -20.0, "style": "red"},
        ]
    )
    for it in items:
        it["use_prims"] = True
    return items


def reception_layout() -> list[dict]:
    """Grey L-desk from the Skyarch office interior video."""
    h = 4.05
    items = [
        {"object_id": "desk_001", "label": "desk", "X": 0.0, "Z": 0.0, "yaw": 0.0, "style": "l_desk"},
        {"object_id": "chair_001", "label": "chair", "X": -2.0, "Z": 0.35, "yaw": -90.0},
        {"object_id": "chair_002", "label": "guest_chair", "X": 11.9, "Z": -3.15, "yaw": 90.0},
        {"object_id": "chair_003", "label": "guest_chair", "X": 11.9, "Z": 2.55, "yaw": 90.0},
        {"object_id": "monitor_001", "label": "monitor", "X": 5.7, "Z": 1.35, "yaw": 90.0, "lift": h},
        {"object_id": "monitor_002", "label": "monitor", "X": 5.7, "Z": 3.35, "yaw": 90.0, "lift": h},
        {"object_id": "plant_001", "label": "plant", "X": -11.2, "Z": 3.4, "yaw": 0.0},
    ]
    for it in items:
        it["use_prims"] = True
    return items


def bedroom_layout() -> list[dict]:
    """Hotel bedroom video: bed + nightstands, lounge chairs by the window, vanity left."""
    ns_x = BED_WID / 2 + 2.7
    ns_z = BED_LEN * 0.5 - 2.4
    pillow_z = BED_LEN * 0.5 - 4.0
    win_x = BED_WID / 2 + 8.4
    vanity_x = -(BED_WID / 2 + 9.2)
    items = [
        {"object_id": "bed_001", "label": "bed", "X": 0.0, "Z": 0.0, "yaw": 0.0},
        {"object_id": "pillow_001", "label": "pillow", "X": -5.1, "Z": pillow_z, "yaw": 0.0, "lift": BED_H},
        {"object_id": "pillow_002", "label": "pillow", "X": -1.7, "Z": pillow_z, "yaw": 4.0, "lift": BED_H},
        {"object_id": "pillow_003", "label": "pillow", "X": 1.7, "Z": pillow_z, "yaw": -4.0, "lift": BED_H},
        {"object_id": "pillow_004", "label": "pillow", "X": 5.1, "Z": pillow_z, "yaw": 0.0, "lift": BED_H},
        {"object_id": "nightstand_001", "label": "nightstand", "X": -ns_x, "Z": ns_z, "yaw": 0.0},
        {"object_id": "nightstand_002", "label": "nightstand", "X": ns_x, "Z": ns_z, "yaw": 0.0},
        {"object_id": "lamp_001", "label": "lamp", "X": -ns_x, "Z": ns_z, "yaw": 0.0, "lift": 3.75},
        {"object_id": "lamp_002", "label": "lamp", "X": ns_x, "Z": ns_z, "yaw": 0.0, "lift": 3.75},
        # Window seating — RIGHT of bed, round table BETWEEN the two chairs.
        {"object_id": "chair_001", "label": "accent_chair", "X": win_x, "Z": -5.6, "yaw": 110.0},
        {"object_id": "chair_002", "label": "accent_chair", "X": win_x, "Z": 5.6, "yaw": 70.0},
        {"object_id": "table_001", "label": "round_table", "X": win_x + 0.2, "Z": 0.0, "yaw": 0.0},
        # Vanity wall — LEFT of bed (seen when the camera pans).
        {"object_id": "vanity_001", "label": "vanity", "X": vanity_x, "Z": 1.2, "yaw": 90.0},
        {"object_id": "chair_003", "label": "vanity_chair", "X": vanity_x + 3.1, "Z": 1.2, "yaw": -90.0},
        {"object_id": "mirror_001", "label": "mirror", "X": vanity_x - 0.4, "Z": 1.2, "yaw": 90.0, "lift": 4.2},
        {"object_id": "clock_001", "label": "clock", "X": -ns_x - 2.4, "Z": BED_LEN / 2 + 0.4, "yaw": 0.0, "lift": 8.0},
    ]
    for it in items:
        it["use_prims"] = True
    return items
