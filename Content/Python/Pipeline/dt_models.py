"""Procedural furniture meshes (OBJ) for the Digital Twin.

TripoSR on room photos produces broken fragments. These models are real
chairs / hex desks / hotel beds so Unreal can spawn recognizable furniture.
Coordinates are written Z-up for Unreal import.
"""

from __future__ import annotations

import math
from pathlib import Path

PRIMARY_COLOR = {
    "desk": (0.72, 0.55, 0.38),
    "table": (0.72, 0.55, 0.38),
    "chair": (0.18, 0.18, 0.20),
    "bed": (0.90, 0.86, 0.80),
    "lamp": (0.85, 0.76, 0.48),
    "nightstand": (0.38, 0.26, 0.18),
    "pillow": (0.93, 0.90, 0.84),
    "couch": (0.32, 0.34, 0.38),
    "curtain": (0.55, 0.52, 0.48),
    "mirror": (0.72, 0.80, 0.86),
    "monitor": (0.10, 0.10, 0.12),
    "laptop": (0.12, 0.12, 0.14),
    "keyboard": (0.12, 0.12, 0.14),
    "mouse": (0.10, 0.10, 0.12),
    "bottle": (0.78, 0.88, 0.92),
    "backpack": (0.10, 0.12, 0.18),
    "plant": (0.22, 0.46, 0.26),
    "paper": (0.95, 0.95, 0.94),
    "book": (0.45, 0.18, 0.16),
    "cell phone": (0.08, 0.08, 0.10),
}

C_WOOD = (0.72, 0.55, 0.38)
C_WOOD_DARK = (0.42, 0.28, 0.18)
C_METAL = (0.78, 0.80, 0.82)
C_BLACK = (0.10, 0.10, 0.12)
C_GREY = (0.52, 0.53, 0.55)
C_FABRIC = (0.38, 0.39, 0.41)
C_CREAM = (0.92, 0.88, 0.80)
C_LINEN = (0.88, 0.84, 0.76)
C_HEAD = (0.42, 0.38, 0.34)
C_GOLD = (0.82, 0.70, 0.38)
C_SHADE = (0.93, 0.88, 0.72)
C_LEAF = (0.20, 0.46, 0.26)
C_SCREEN = (0.08, 0.16, 0.28)


class MeshBuilder:
    """Triangle mesh, Unreal Z-up (X right, Y forward, Z up)."""

    def __init__(self):
        self.verts: list[tuple[float, float, float]] = []
        self.faces: list[tuple[int, int, int]] = []
        self.colors: list[tuple[float, float, float]] = []

    def _v(self, x, y, z, rgb):
        self.verts.append((float(x), float(y), float(z)))
        self.colors.append(tuple(float(c) for c in rgb))
        return len(self.verts) - 1

    def tri(self, a, b, c):
        self.faces.append((a, b, c))

    def quad(self, a, b, c, d):
        self.tri(a, b, c)
        self.tri(a, c, d)

    def box(self, xmin, xmax, ymin, ymax, zmin, zmax, rgb):
        p = [
            self._v(xmin, ymin, zmin, rgb),
            self._v(xmax, ymin, zmin, rgb),
            self._v(xmax, ymax, zmin, rgb),
            self._v(xmin, ymax, zmin, rgb),
            self._v(xmin, ymin, zmax, rgb),
            self._v(xmax, ymin, zmax, rgb),
            self._v(xmax, ymax, zmax, rgb),
            self._v(xmin, ymax, zmax, rgb),
        ]
        self.quad(p[0], p[1], p[2], p[3])
        self.quad(p[4], p[7], p[6], p[5])
        self.quad(p[0], p[4], p[5], p[1])
        self.quad(p[2], p[6], p[7], p[3])
        self.quad(p[1], p[5], p[6], p[2])
        self.quad(p[0], p[3], p[7], p[4])

    def yup_box(self, xmin, xmax, ymin, ymax, zmin, zmax, rgb):
        """Y-up furniture box (X, height Y, depth Z) → Unreal Z-up."""
        self.box(xmin, xmax, zmin, zmax, ymin, ymax, rgb)

    def cylinder(self, cx, cy, z0, radius, height, rgb, segs=18):
        top = z0 + height
        ring0 = []
        ring1 = []
        for i in range(segs):
            a = (2.0 * math.pi * i) / segs
            x = cx + radius * math.cos(a)
            y = cy + radius * math.sin(a)
            ring0.append(self._v(x, y, z0, rgb))
            ring1.append(self._v(x, y, top, rgb))
        c0 = self._v(cx, cy, z0, rgb)
        c1 = self._v(cx, cy, top, rgb)
        for i in range(segs):
            j = (i + 1) % segs
            self.quad(ring0[i], ring0[j], ring1[j], ring1[i])
            self.tri(c0, ring0[j], ring0[i])
            self.tri(c1, ring1[i], ring1[j])

    def yup_cyl(self, cx, y0, cz, radius, height, rgb, segs=18):
        self.cylinder(cx, cz, y0, radius, height, rgb, segs)

    def frustum(self, cx, cy, z0, r0, r1, height, rgb, segs=16):
        top = z0 + height
        ring0, ring1 = [], []
        for i in range(segs):
            a = (2.0 * math.pi * i) / segs
            ca, sa = math.cos(a), math.sin(a)
            ring0.append(self._v(cx + r0 * ca, cy + r0 * sa, z0, rgb))
            ring1.append(self._v(cx + r1 * ca, cy + r1 * sa, top, rgb))
        c0 = self._v(cx, cy, z0, rgb)
        c1 = self._v(cx, cy, top, rgb)
        for i in range(segs):
            j = (i + 1) % segs
            self.quad(ring0[i], ring0[j], ring1[j], ring1[i])
            self.tri(c0, ring0[j], ring0[i])
            self.tri(c1, ring1[i], ring1[j])

    def prism(self, cx, cy, z0, radius, height, rgb, sides=6, rotation=0.0):
        top = z0 + height
        ring0, ring1 = [], []
        for i in range(sides):
            a = rotation + (2.0 * math.pi * i) / sides
            x = cx + radius * math.cos(a)
            y = cy + radius * math.sin(a)
            ring0.append(self._v(x, y, z0, rgb))
            ring1.append(self._v(x, y, top, rgb))
        c0 = self._v(cx, cy, z0, rgb)
        c1 = self._v(cx, cy, top, rgb)
        for i in range(sides):
            j = (i + 1) % sides
            self.quad(ring0[i], ring0[j], ring1[j], ring1[i])
            self.tri(c0, ring0[j], ring0[i])
            self.tri(c1, ring1[i], ring1[j])

    def write(self, path: Path, material_rgb=(0.7, 0.7, 0.7)):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        mtl = path.with_suffix(".mtl")
        r, g, b = material_rgb
        mtl.write_text(
            "newmtl furniture\nKd {:.4f} {:.4f} {:.4f}\nKa 0.05 0.05 0.05\nKs 0.08 0.08 0.08\nNs 12\nillum 2\n".format(
                r, g, b
            ),
            encoding="utf-8",
        )
        lines = [
            "# Digital Twin Builder furniture",
            "mtllib {}".format(mtl.name),
            "usemtl furniture",
        ]
        for (x, y, z), (cr, cg, cb) in zip(self.verts, self.colors):
            lines.append(
                "v {:.5f} {:.5f} {:.5f} {:.4f} {:.4f} {:.4f}".format(x, y, z, cr, cg, cb)
            )
        for a, b, c in self.faces:
            lines.append("f {} {} {}".format(a + 1, b + 1, c + 1))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path


def _hex_desk(m: MeshBuilder):
    radius = 6.8
    m.prism(0.0, 0.0, 4.00, radius, 0.28, C_WOOD, sides=6, rotation=math.radians(30))
    m.prism(0.0, 0.0, 3.94, radius + 0.08, 0.06, (0.55, 0.40, 0.26), sides=6, rotation=math.radians(30))
    for i in (0, 2, 4):
        a = math.radians(30 + i * 60)
        lx = 4.6 * math.cos(a)
        ly = 4.6 * math.sin(a)
        m.cylinder(lx, ly, 0.0, 0.22, 4.00, C_METAL, segs=14)
        m.cylinder(lx, ly, 0.0, 0.32, 0.12, (0.88, 0.88, 0.90), segs=12)


def _office_chair(m: MeshBuilder):
    m.yup_box(-1.85, 1.85, 2.55, 3.05, -1.75, 1.75, C_FABRIC)
    m.yup_box(-1.70, 1.70, 3.05, 6.85, -1.95, -1.15, C_GREY)
    m.yup_box(-1.55, 1.55, 5.40, 6.70, -1.15, -0.85, C_GREY)
    m.yup_box(-2.15, -1.70, 3.15, 4.05, -1.20, 1.35, C_BLACK)
    m.yup_box(1.70, 2.15, 3.15, 4.05, -1.20, 1.35, C_BLACK)
    m.yup_cyl(0.0, 1.15, 0.0, 0.22, 1.45, C_METAL, segs=14)
    m.yup_cyl(0.0, 0.95, 0.0, 0.55, 0.28, C_BLACK, segs=14)
    for deg in range(0, 360, 72):
        a = math.radians(deg)
        sx, sz = 2.35 * math.cos(a), 2.35 * math.sin(a)
        m.yup_box(-0.16 + sx * 0.35, 0.16 + sx * 0.35, 0.28, 0.50, -0.16 + sz * 0.35, 0.16 + sz * 0.35, C_BLACK)
        m.yup_box(-0.18 + sx, 0.18 + sx, 0.22, 0.48, -0.18 + sz, 0.18 + sz, C_BLACK)
        m.yup_cyl(sx, 0.0, sz, 0.32, 0.22, C_BLACK, segs=10)


def _luxury_bed(m: MeshBuilder):
    m.yup_box(-8.6, 8.6, 0.0, 1.35, -6.8, 6.4, C_WOOD_DARK)
    m.yup_box(-8.3, 8.3, 1.35, 3.15, -6.5, 6.1, C_CREAM)
    m.yup_box(-8.0, 8.0, 3.05, 3.55, -6.2, 5.4, C_LINEN)
    m.yup_box(-8.8, 8.8, 0.0, 7.6, 6.1, 7.15, C_HEAD)
    m.yup_box(-8.5, 8.5, 1.4, 7.2, 6.05, 6.55, (0.50, 0.46, 0.40))
    m.yup_box(-7.4, -1.2, 3.50, 4.55, 4.4, 6.05, (0.94, 0.91, 0.86))
    m.yup_box(1.2, 7.4, 3.50, 4.55, 4.4, 6.05, (0.94, 0.91, 0.86))


def _lamp(m: MeshBuilder):
    m.yup_cyl(0.0, 0.0, 0.0, 0.85, 0.22, C_GOLD, segs=16)
    m.yup_cyl(0.0, 0.22, 0.0, 0.10, 5.4, C_METAL, segs=12)
    m.frustum(0.0, 0.0, 5.45, 1.25, 0.55, 2.15, C_SHADE, segs=16)
    m.yup_cyl(0.0, 5.35, 0.0, 0.18, 0.18, C_GOLD, segs=10)


def _nightstand(m: MeshBuilder):
    m.yup_box(-1.85, 1.85, 0.0, 4.15, -1.75, 1.75, C_WOOD_DARK)
    m.yup_box(-1.70, 1.70, 2.05, 3.85, -1.55, 1.78, (0.30, 0.20, 0.14))
    m.yup_box(-0.28, 0.28, 2.80, 3.05, 1.70, 1.88, C_GOLD)
    m.yup_box(-1.90, 1.90, 4.15, 4.40, -1.80, 1.80, (0.48, 0.32, 0.20))


def _pillow(m: MeshBuilder):
    m.yup_box(-1.9, 1.9, 0.0, 1.05, -1.35, 1.35, (0.93, 0.90, 0.84))
    m.yup_box(-1.6, 1.6, 0.85, 1.20, -1.10, 1.10, (0.96, 0.93, 0.88))


def _couch(m: MeshBuilder):
    m.yup_box(-6.8, 6.8, 0.0, 2.35, -2.8, 2.8, C_FABRIC)
    m.yup_box(-6.8, 6.8, 2.35, 5.1, 1.85, 2.85, C_GREY)
    m.yup_box(-6.9, -5.55, 2.35, 4.4, -2.4, 1.85, C_GREY)
    m.yup_box(5.55, 6.9, 2.35, 4.4, -2.4, 1.85, C_GREY)
    m.yup_box(-2.4, -0.3, 2.35, 3.15, -2.2, 1.4, (0.88, 0.84, 0.76))
    m.yup_box(0.3, 2.4, 2.35, 3.15, -2.2, 1.4, (0.88, 0.84, 0.76))


def _laptop(m: MeshBuilder):
    m.yup_box(-2.15, 2.15, 0.0, 0.18, -1.45, 1.45, C_BLACK)
    m.yup_box(-2.05, 2.05, 0.18, 2.85, -1.55, -1.22, C_BLACK)
    m.yup_box(-1.85, 1.85, 0.35, 2.65, -1.50, -1.32, C_SCREEN)


def _monitor(m: MeshBuilder):
    m.yup_box(-1.4, 1.4, 0.0, 0.18, -0.9, 0.9, C_BLACK)
    m.yup_box(-0.35, 0.35, 0.0, 1.35, -0.25, 0.25, C_BLACK)
    m.yup_box(-2.75, 2.75, 1.35, 5.15, -0.14, 0.14, C_BLACK)
    m.yup_box(-2.55, 2.55, 1.50, 4.95, -0.08, 0.12, C_SCREEN)


def _keyboard(m: MeshBuilder):
    m.yup_box(-2.15, 2.15, 0.0, 0.18, -0.85, 0.85, C_BLACK)
    for i in range(-4, 5):
        for j in range(-1, 2):
            m.yup_box(i * 0.42 - 0.12, i * 0.42 + 0.12, 0.18, 0.28, j * 0.38 - 0.10, j * 0.38 + 0.10, (0.18, 0.18, 0.20))


def _mouse(m: MeshBuilder):
    m.yup_box(-0.42, 0.42, 0.0, 0.28, -0.70, 0.70, C_BLACK)
    m.yup_cyl(0.0, 0.18, 0.15, 0.22, 0.16, (0.16, 0.16, 0.18), segs=10)


def _bottle(m: MeshBuilder):
    m.yup_cyl(0.0, 0.0, 0.0, 0.38, 1.55, (0.78, 0.88, 0.92), segs=14)
    m.yup_cyl(0.0, 1.55, 0.0, 0.18, 0.55, (0.70, 0.80, 0.86), segs=12)
    m.yup_cyl(0.0, 2.05, 0.0, 0.22, 0.22, (0.85, 0.20, 0.18), segs=12)


def _backpack(m: MeshBuilder):
    m.yup_box(-1.45, 1.45, 0.15, 4.15, -1.05, 1.05, (0.10, 0.12, 0.18))
    m.yup_box(-1.20, 1.20, 1.6, 3.4, 0.95, 1.25, (0.08, 0.08, 0.12))
    m.yup_cyl(-0.85, 0.0, 0.0, 0.22, 0.20, C_BLACK, segs=8)
    m.yup_cyl(0.85, 0.0, 0.0, 0.22, 0.20, C_BLACK, segs=8)


def _plant(m: MeshBuilder):
    m.yup_cyl(0.0, 0.0, 0.0, 0.85, 1.35, (0.45, 0.32, 0.22), segs=14)
    m.yup_cyl(0.0, 1.20, 0.0, 1.15, 1.6, C_LEAF, segs=12)
    m.yup_cyl(0.35, 2.4, 0.2, 0.85, 1.8, (0.18, 0.42, 0.22), segs=10)
    m.yup_cyl(-0.30, 2.2, -0.15, 0.75, 1.6, (0.24, 0.50, 0.28), segs=10)


def _mirror(m: MeshBuilder):
    m.yup_box(-1.85, 1.85, 0.4, 7.6, -0.12, 0.12, C_METAL)
    m.yup_box(-1.65, 1.65, 0.6, 7.4, -0.04, 0.14, (0.70, 0.80, 0.88))


def _curtain(m: MeshBuilder):
    m.yup_box(-2.8, 2.8, 0.0, 13.6, -0.18, 0.18, (0.55, 0.50, 0.44))
    m.yup_box(-2.9, 2.9, 13.4, 13.9, -0.22, 0.22, C_WOOD_DARK)


def _paper(m: MeshBuilder):
    m.yup_box(-1.35, 1.35, 0.0, 0.04, -1.7, 1.7, (0.96, 0.96, 0.95))


def _book(m: MeshBuilder):
    m.yup_box(-1.1, 1.1, 0.0, 0.28, -1.5, 1.5, (0.45, 0.16, 0.14))
    m.yup_box(-1.0, 1.0, 0.04, 0.24, -1.4, 1.45, (0.93, 0.90, 0.84))


def _phone(m: MeshBuilder):
    m.yup_box(-0.55, 0.55, 0.0, 0.10, -1.05, 1.05, C_BLACK)
    m.yup_box(-0.45, 0.45, 0.08, 0.12, -0.90, 0.90, C_SCREEN)


BUILDERS = {
    "desk": _hex_desk,
    "table": _hex_desk,
    "chair": _office_chair,
    "bed": _luxury_bed,
    "lamp": _lamp,
    "nightstand": _nightstand,
    "pillow": _pillow,
    "couch": _couch,
    "laptop": _laptop,
    "monitor": _monitor,
    "tv": _monitor,
    "keyboard": _keyboard,
    "mouse": _mouse,
    "bottle": _bottle,
    "backpack": _backpack,
    "plant": _plant,
    "potted plant": _plant,
    "mirror": _mirror,
    "curtain": _curtain,
    "paper": _paper,
    "book": _book,
    "cell phone": _phone,
    "phone": _phone,
}


def write_furniture_mesh(label: str, dest_dir: Path) -> Path | None:
    fn = BUILDERS.get(label)
    if fn is None:
        return None
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe = "".join(ch if ch.isalnum() else "_" for ch in label)
    path = dest_dir / "{}.obj".format(safe)
    mesh = MeshBuilder()
    fn(mesh)
    if not mesh.faces:
        return None
    mesh.write(path, PRIMARY_COLOR.get(label, (0.65, 0.65, 0.65)))
    return path


def attach_library_meshes(items: list[dict], work_dir: Path, progress=None) -> list[dict]:
    dest = Path(work_dir) / "library_meshes"
    cache: dict[str, str] = {}
    labels = sorted({it["label"] for it in items})
    for i, lab in enumerate(labels):
        if progress:
            progress(70 + int(16 * (i / max(len(labels), 1))), "Furniture mesh: {}".format(lab))
        if lab not in cache:
            path = write_furniture_mesh(lab, dest)
            if path is not None:
                cache[lab] = str(path.resolve())
                print("Library mesh {}: {}".format(lab, path), flush=True)
            else:
                print("No library mesh for {}".format(lab), flush=True)
    for it in items:
        mp = cache.get(it["label"])
        if mp:
            it["mesh_path"] = mp
            it["mesh_source"] = "library"
            it["color"] = list(PRIMARY_COLOR.get(it["label"], (0.65, 0.65, 0.65)))
    if progress:
        progress(88, "Furniture meshes: {}/{} labels".format(len(cache), len(labels)))
    return items
