"""Write a Plotly HTML preview from unreal_scene.json so a twin can be inspected without Unreal."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import plotly.graph_objects as go


def _box(cx, cy, cz, sx, sy, sz, rgb, yaw_deg=0.0):
    hx, hy, hz = sx * 0.5, sy * 0.5, sz * 0.5
    v = np.array(
        [
            [-hx, -hy, -hz],
            [hx, -hy, -hz],
            [hx, -hy, hz],
            [-hx, -hy, hz],
            [-hx, hy, -hz],
            [hx, hy, -hz],
            [hx, hy, hz],
            [-hx, hy, hz],
        ],
        float,
    )
    if abs(yaw_deg) > 1e-6:
        a = np.deg2rad(float(yaw_deg))
        ca, sa = np.cos(a), np.sin(a)
        x, z = v[:, 0].copy(), v[:, 2].copy()
        v[:, 0] = ca * x - sa * z
        v[:, 2] = sa * x + ca * z
    v[:, 0] += cx
    v[:, 1] += cy
    v[:, 2] += cz
    f = np.array(
        [
            [0, 1, 2],
            [0, 2, 3],
            [4, 6, 5],
            [4, 7, 6],
            [0, 4, 5],
            [0, 5, 1],
            [3, 2, 6],
            [3, 6, 7],
            [0, 3, 7],
            [0, 7, 4],
            [1, 5, 6],
            [1, 6, 2],
        ],
        int,
    )
    c = np.tile(np.asarray(rgb, float), (8, 1))
    return v, f, c


def _cyl(cx, cy, cz, sx, sy, sz, rgb, segs=18):
    rx, rz = max(sx * 0.5, 0.05), max(sz * 0.5, 0.05)
    y0, y1 = cy - sy * 0.5, cy + sy * 0.5
    ang = np.linspace(0, 2 * np.pi, segs, endpoint=False)
    bot = np.stack([cx + rx * np.cos(ang), np.full(segs, y0), cz + rz * np.sin(ang)], 1)
    top = bot.copy()
    top[:, 1] = y1
    cb = np.array([[cx, y0, cz]])
    ct = np.array([[cx, y1, cz]])
    v = np.vstack([cb, bot, ct, top])
    f = []
    for i in range(segs):
        a, b = 1 + i, 1 + (i + 1) % segs
        f.append([0, b, a])
    mid = 1 + segs
    for i in range(segs):
        a, b = mid + 1 + i, mid + 1 + (i + 1) % segs
        f.append([mid, a, b])
        f.append([1 + i, 1 + (i + 1) % segs, b])
        f.append([1 + i, b, mid + 1 + i])
    c = np.tile(np.asarray(rgb, float), (len(v), 1))
    return v, np.asarray(f, int), c


def _load_obj(path: Path, tex_path: Path | None = None, coord: str = "y_up"):
    """Load an OBJ into plotly arrays (x, y_depth, z_up)."""
    verts = []
    uvs = []
    faces = []
    y_up = str(coord or "y_up").lower() not in {"z_up", "unreal_zup"}
    for raw in Path(path).read_text(encoding="utf-8", errors="ignore").splitlines():
        if "coord y_up" in raw:
            y_up = True
        elif "coord z_up" in raw or "coord unreal_zup" in raw:
            y_up = False
        if raw.startswith("v "):
            p = raw.split()
            verts.append([float(p[1]), float(p[2]), float(p[3])])
        elif raw.startswith("vt "):
            p = raw.split()
            uvs.append([float(p[1]), float(p[2])])
        elif raw.startswith("f "):
            ids = []
            for tok in raw.split()[1:]:
                bits = tok.split("/")
                ids.append(int(bits[0]) - 1)
            if len(ids) >= 3:
                faces.append(ids[:3])
                if len(ids) == 4:
                    faces.append([ids[0], ids[2], ids[3]])
    V = np.asarray(verts, float)
    if len(V) and y_up:
        # OBJ Y-up (x, height, depth) → plotly (x, depth, height)
        V = np.column_stack([V[:, 0], V[:, 2], V[:, 1]])
    F = np.asarray(faces, int) if faces else np.zeros((0, 3), int)
    C = np.full((len(V), 3), 0.72, float)
    tex = None
    if tex_path and Path(tex_path).is_file():
        import cv2

        tex = cv2.cvtColor(cv2.imread(str(tex_path)), cv2.COLOR_BGR2RGB)
    if tex is not None and uvs and len(V):
        th, tw = tex.shape[:2]
        UV = np.asarray(uvs, float)
        n = min(len(V), len(UV))
        uu = np.clip(UV[:n, 0], 0, 1) * (tw - 1)
        vv = np.clip(1.0 - UV[:n, 1], 0, 1) * (th - 1)
        C[:n] = tex[vv.astype(int), uu.astype(int)] / 255.0
    return V, F, C


def plot_scene(scene_path: Path, html_path: Path) -> Path:
    doc = json.loads(scene_path.read_text(encoding="utf-8"))
    actors = doc.get("actors") or []
    src = doc.get("source") or {}
    recon = doc.get("reconstruction") or {}
    traces = []
    obj_path = recon.get("obj_path")
    mesh_bounds = None
    if obj_path and Path(obj_path).is_file():
        V, F, C = _load_obj(
            Path(obj_path),
            Path(recon["tex_path"]) if recon.get("tex_path") else None,
            recon.get("coord") or "y_up",
        )
        if len(V) and len(F):
            mesh_bounds = (V.min(0), V.max(0))
            traces.append(
                go.Mesh3d(
                    x=V[:, 0],
                    y=V[:, 1],
                    z=V[:, 2],
                    i=F[:, 0],
                    j=F[:, 1],
                    k=F[:, 2],
                    vertexcolor=C,
                    flatshading=True,
                    lighting=dict(ambient=0.92, diffuse=0.35, specular=0.0),
                    hoverinfo="skip",
                    name="scene",
                )
            )
    parts = []
    if mesh_bounds is None:
        src = doc.get("source") or {}
        is_bed = src.get("scene_kind") == "bedroom"
        is_kit = src.get("scene_kind") == "kitchen"
        floor = (0.82, 0.76, 0.68) if is_kit else ((0.50, 0.44, 0.36) if is_bed else (0.62, 0.63, 0.65))
        parts.append(_box(0.0, -0.08, 0.0, 36.0, 0.16, 28.0, floor))
    for a in actors:
        if a.get("label") == "scene" or a.get("id") == "scene_mesh":
            continue
        loc = a.get("location") or [0, 0, 0]
        sc = a.get("scale") or [2, 2, 2]
        rgb = a.get("color") or (0.55, 0.55, 0.58)
        yaw = float(a.get("yaw_deg") or 0.0)
        shape = (a.get("shape") or "box").lower()
        if shape == "imported":
            continue
        if shape == "cylinder":
            parts.append(_cyl(loc[0], loc[1], loc[2], sc[0], sc[1], sc[2], rgb))
        else:
            parts.append(_box(loc[0], loc[1], loc[2], sc[0], sc[1], sc[2], rgb, yaw))
    if parts:
        verts, faces, cols = [], [], []
        base = 0
        for v, f, c in parts:
            verts.append(v)
            faces.append(f + base)
            cols.append(c)
            base += len(v)
        V, F, C = np.vstack(verts), np.vstack(faces), np.vstack(cols)
        traces.append(
            go.Mesh3d(
                x=V[:, 0],
                y=V[:, 2],
                z=V[:, 1],
                i=F[:, 0],
                j=F[:, 1],
                k=F[:, 2],
                vertexcolor=C,
                flatshading=True,
                lighting=dict(ambient=0.7, diffuse=0.8, specular=0.1),
                hoverinfo="skip",
                name="furniture",
            )
        )
    fig = go.Figure(data=traces)
    title = "Digital twin — {} ({})".format(
        src.get("scene_kind", "scene"),
        src.get("pipeline", ""),
    )
    has_photo = bool(mesh_bounds)
    if has_photo:
        axis = dict(
            showbackground=False,
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            title="",
            visible=False,
        )
        eye = (recon.get("camera_eye") or {}) if recon else {}
        cam = dict(
            up=dict(x=0, y=0, z=1),
            center=dict(x=0, y=0.12, z=0.02),
            eye=dict(
                x=float(eye.get("x", 0.0)),
                y=float(eye.get("y", -1.65)),
                z=float(eye.get("z", 0.08)),
            ),
        )
    else:
        axis = dict(
            showbackground=True,
            backgroundcolor="rgb(245,245,248)",
            gridcolor="rgb(210,210,218)",
            title="",
        )
        cam = dict(eye=dict(x=0.18, y=-1.55, z=1.15))
    fig.update_layout(
        title=title,
        scene=dict(
            aspectmode="data",
            xaxis={**axis, "title": "X"} if not has_photo else axis,
            yaxis={**axis, "title": "Z"} if not has_photo else axis,
            zaxis={**axis, "title": "Y"} if not has_photo else axis,
            camera=cam,
        ),
        margin=dict(l=0, r=0, t=40, b=0),
        paper_bgcolor="white",
    )
    html_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(html_path), include_plotlyjs="cdn")
    try:
        plot_topdown(doc, html_path.with_name("topdown.png"))
    except Exception:
        pass
    return html_path


def plot_topdown(doc: dict, png_path: Path) -> Path:
    """Orthographic floor plan matching the furniture twin."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, FancyBboxPatch, Rectangle

    src = doc.get("source") or {}
    actors = doc.get("actors") or []
    is_bed = src.get("scene_kind") == "bedroom"
    is_kit = src.get("scene_kind") == "kitchen"
    floor = (0.82, 0.76, 0.68) if is_kit else ((0.62, 0.55, 0.46) if is_bed else (0.72, 0.73, 0.75))
    fig, ax = plt.subplots(figsize=(8.2, 6.4), dpi=140)
    xs, zs = [], []
    for a in actors:
        if a.get("label") in {"scene", "floor"} or a.get("id") == "scene_mesh":
            continue
        loc = a.get("location") or [0, 0, 0]
        sc = a.get("scale") or [2, 2, 2]
        xs.extend([loc[0] - sc[0] * 0.5, loc[0] + sc[0] * 0.5])
        zs.extend([loc[2] - sc[2] * 0.5, loc[2] + sc[2] * 0.5])
    pad = 4.0
    if not xs:
        xs, zs = [-16, 16], [-12, 12]
    xmin, xmax = min(xs) - pad, max(xs) + pad
    zmin, zmax = min(zs) - pad, max(zs) + pad
    ax.add_patch(Rectangle((xmin, zmin), xmax - xmin, zmax - zmin, facecolor=floor, edgecolor="none", zorder=0))
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(zmin, zmax)
    ax.set_aspect("equal")
    ax.set_xlabel("X")
    ax.set_ylabel("Z")
    ax.set_title(png_path.parent.name)
    ax.grid(True, color=(1, 1, 1, 0.35), linewidth=0.6)
    for a in actors:
        if a.get("label") in {"scene", "floor"} or a.get("id") == "scene_mesh":
            continue
        loc = a.get("location") or [0, 0, 0]
        sc = a.get("scale") or [2, 2, 2]
        rgb = a.get("color") or (0.45, 0.45, 0.48)
        yaw = float(a.get("yaw_deg") or 0.0)
        shape = (a.get("shape") or "box").lower()
        w, d = float(sc[0]), float(sc[2])
        if shape == "cylinder":
            ax.add_patch(
                Circle((loc[0], loc[2]), max(w, d) * 0.5, facecolor=rgb, edgecolor="none", zorder=2)
            )
        else:
            patch = FancyBboxPatch(
                (loc[0] - w * 0.5, loc[2] - d * 0.5),
                w,
                d,
                boxstyle="square,pad=0",
                facecolor=rgb,
                edgecolor="none",
                zorder=2,
            )
            if abs(yaw) > 0.5:
                patch.set_transform(
                    matplotlib.transforms.Affine2D().rotate_deg_around(loc[0], loc[2], yaw) + ax.transData
                )
            else:
                patch.set_transform(ax.transData)
            ax.add_patch(patch)
    fig.tight_layout()
    png_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(png_path), bbox_inches="tight")
    plt.close(fig)
    return png_path


if __name__ == "__main__":
    scene = Path(sys.argv[1])
    html = Path(sys.argv[2]) if len(sys.argv) > 2 else scene.with_name("digital_twin.html")
    out = plot_scene(scene, html)
    print("HTML:{}".format(out), flush=True)
