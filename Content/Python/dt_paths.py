"""Resolve plugin / project paths from this plugin folder only.

Sharing Plugins/DigitalTwinBuilder must work. Do not look under
Content/python/EditorTools or AutomatedSyntheticDataPipeline.
"""

from __future__ import annotations

import os

import unreal

try:
    _THIS_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _THIS_DIR = None


def norm(path: str) -> str:
    if not path:
        return ""
    return os.path.normpath(os.path.abspath(path))


def is_project_root(path: str) -> bool:
    if not path or not os.path.isdir(path):
        return False
    if ".." in path.replace("\\", "/").split("/"):
        return False
    if os.path.isdir(os.path.join(path, "Content")):
        return True
    try:
        return any(name.endswith(".uproject") for name in os.listdir(path))
    except Exception:
        return False


def plugin_python_dir() -> str:
    """Plugins/DigitalTwinBuilder/Content/Python"""
    if _THIS_DIR:
        return norm(_THIS_DIR)
    raise RuntimeError("DigitalTwinBuilder plugin Python folder could not be resolved.")


def pipeline_dir() -> str:
    """Bundled preprocess scripts live next to the editor glue."""
    return norm(os.path.join(plugin_python_dir(), "Pipeline"))


def project_dir() -> str:
    """Host project root (wherever this plugin was copied)."""
    candidates = []

    if _THIS_DIR:
        # Content/Python → Content → plugin → Plugins → project
        candidates.append(norm(os.path.join(_THIS_DIR, "..", "..", "..", "..")))

    raw = ""
    try:
        raw = unreal.Paths.project_dir() or ""
    except Exception:
        raw = ""

    if raw:
        try:
            candidates.append(norm(unreal.Paths.convert_relative_path_to_full(raw)))
        except Exception:
            pass
        abs_raw = norm(raw)
        if ".." not in abs_raw.replace("\\", "/"):
            candidates.append(abs_raw)

    for c in candidates:
        if is_project_root(c):
            return c

    if _THIS_DIR:
        cur = _THIS_DIR
        for _ in range(8):
            if is_project_root(cur):
                return cur
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent

    raise RuntimeError(
        "Could not resolve the Unreal project directory. "
        "Keep this plugin at Plugins/DigitalTwinBuilder/"
    )


def export_script_path() -> str:
    return norm(os.path.join(pipeline_dir(), "export_unreal_scene.py"))


def output_run_dir() -> str:
    return norm(os.path.join(project_dir(), "Saved", "DigitalTwin", "last_run"))


def logs_dir() -> str:
    return norm(os.path.join(project_dir(), "Saved", "Logs"))
