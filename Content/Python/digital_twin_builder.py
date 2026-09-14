"""
Digital Twin Builder — Unreal Editor entry (plugin).

Loads sibling modules from THIS folder only so EditorTools copies cannot steal imports.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import traceback

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_local(name: str):
    path = os.path.join(_HERE, name + ".py")
    key = "dtb_plugin_" + name
    spec = importlib.util.spec_from_file_location(key, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


# Drop the old EditorTools folder so `import dt_paths` cannot resolve there.
_cleaned = []
for _p in sys.path:
    normp = os.path.normpath(_p).lower()
    if "editortools" in normp and "digitaltwinbuilder" in normp:
        continue
    _cleaned.append(_p)
sys.path[:] = _cleaned
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

for _stale in ("dt_paths", "dt_picker", "dt_progress", "dt_materials", "dt_spawn"):
    sys.modules.pop(_stale, None)

dt_paths = _load_local("dt_paths")
dt_picker = _load_local("dt_picker")
dt_progress = _load_local("dt_progress")
dt_spawn = _load_local("dt_spawn")

import unreal  # noqa: E402

export_script_path = dt_paths.export_script_path
norm = dt_paths.norm
pipeline_dir = dt_paths.pipeline_dir
plugin_python_dir = dt_paths.plugin_python_dir
project_dir = dt_paths.project_dir
output_run_dir = dt_paths.output_run_dir
pick_media_files = dt_picker.pick_media_files
show_message = dt_picker.show_message
ProgressPump = dt_progress.ProgressPump
close_log = dt_progress.close_log
create_log_file = dt_progress.create_log_file
find_python_cmd = dt_progress.find_python_cmd
get_log_file_path = dt_progress.get_log_file_path
log_line = dt_progress.log_line
open_output_log = dt_progress.open_output_log
spawn_scene_from_json = dt_spawn.spawn_scene_from_json
lock_twin_camera = dt_spawn.lock_twin_camera
release_twin_camera = dt_spawn.release_twin_camera

_ACTIVE_SESSION = None


def _on_preprocess_finished(pump):
    global _ACTIVE_SESSION
    log_file = pump.log_file
    try:
        if pump.return_code not in (0, None):
            msg = "Preprocess failed (exit {}). See Output Log.".format(pump.return_code)
            log_line("[DigitalTwin] ERROR: {}".format(msg), log_file)
            show_message("Digital Twin — Failed", msg)
            return

        scene_json = pump.scene_json
        if not scene_json or not os.path.isfile(scene_json):
            candidate = norm(os.path.join(pump.out_dir, "unreal_scene.json"))
            if os.path.isfile(candidate):
                scene_json = candidate
        if not scene_json or not os.path.isfile(scene_json):
            show_message(
                "Digital Twin — Failed",
                "unreal_scene.json was not produced.\nChecked:\n{}".format(pump.out_dir),
            )
            return

        log_line("[DigitalTwin] Creating Digital Twin level + spawning...", log_file)
        count, level_path = spawn_scene_from_json(scene_json, log_file)
        log_line(
            "[DigitalTwin] DONE — {} actor(s) in {}".format(count, level_path),
            log_file,
        )
        show_message(
            "Digital Twin — Complete",
            "Spawned {} object(s).\n\nLevel:\n{}\n\n"
            "Open Content Browser → DigitalTwin/Maps\n"
            "Move the viewport freely (RMB + WASD).\n\nLog:\n{}".format(
                count, level_path, get_log_file_path() or ""
            ),
        )
    except Exception:
        err = traceback.format_exc()
        log_line(err, log_file)
        show_message("Digital Twin — Error", err[:1500])
    finally:
        close_log(log_file)
        _ACTIVE_SESSION = None


def run():
    global _ACTIVE_SESSION
    unreal.log("[DigitalTwin] === Build Digital Twin started ===")
    try:
        release_twin_camera()
    except Exception:
        pass
    try:
        unreal.log_flush()
    except Exception:
        pass

    if _ACTIVE_SESSION is not None:
        unreal.log("[DigitalTwin] Previous build still marked running — cancelling it.")
        try:
            _ACTIVE_SESSION.cancel()
        except Exception:
            pass
        _ACTIVE_SESSION = None

    paths = pick_media_files()
    if not paths:
        show_message(
            "Digital Twin",
            "No files selected.\n\nPick multiple images (Ctrl+click) or one video, then Open.",
        )
        return

    log_file = None
    try:
        log_file = create_log_file()
        open_output_log()

        plugin_py = plugin_python_dir()
        pipe = pipeline_dir()
        export_py = export_script_path()
        out_dir = output_run_dir()
        work_dir = pipe if os.path.isdir(pipe) else plugin_py

        log_line("[DigitalTwin] Plugin:  {}".format(plugin_py), log_file)
        log_line("[DigitalTwin] Pipeline: {}".format(pipe), log_file)
        log_line("[DigitalTwin] Export:   {}".format(export_py), log_file)
        log_line("[DigitalTwin] Project:  {}".format(project_dir()), log_file)
        log_line("[DigitalTwin] Output:   {}".format(out_dir), log_file)
        log_line("[DigitalTwin] Work dir: {}".format(work_dir), log_file)

        if not os.path.isfile(export_py):
            msg = (
                "Plugin pipeline is incomplete.\n"
                "Missing export_unreal_scene.py:\n{}".format(export_py)
            )
            log_line("[DigitalTwin] ERROR: {}".format(msg), log_file)
            show_message("Digital Twin — Missing Script", msg)
            return

        if os.path.isdir(out_dir):
            shutil.rmtree(out_dir, ignore_errors=True)
        os.makedirs(out_dir, exist_ok=True)

        abs_paths = [norm(p) for p in paths]
        py_cmd = find_python_cmd()
        argv = py_cmd + [
            "-u",
            export_py,
            "--input",
            abs_paths[0],
            "--output",
            out_dir,
        ]
        if len(abs_paths) > 1:
            argv.append("--extra")
            argv.extend(abs_paths[1:])

        os.environ.setdefault("DT_MESH_BACKEND", "prims")
        log_line("[DigitalTwin] Files: {}".format(len(abs_paths)), log_file)
        for p in abs_paths:
            log_line("  - {}".format(p), log_file)
        log_line("[DigitalTwin] Layout: from detections (any scene)", log_file)
        log_line("[DigitalTwin] Cmd: {}".format(subprocess.list2cmdline(argv)), log_file)
        log_line("[DigitalTwin] Preprocess RUNNING...", log_file)

        pump = ProgressPump(argv, work_dir, log_file, out_dir, _on_preprocess_finished)
        _ACTIVE_SESSION = pump
        pump.start()
        log_file = None
    except Exception:
        err = traceback.format_exc()
        if log_file:
            log_line(err, log_file)
        show_message("Digital Twin — Error", err[:1500])
    finally:
        if log_file is not None:
            close_log(log_file)


if __name__ == "__main__":
    run()
