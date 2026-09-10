"""
Digital Twin Builder — Unreal Editor entry (plugin).

All preprocess code lives in this plugin's Content/Python/Pipeline folder.
Does not import from Content/python/EditorTools or ObjectLocator.
"""

from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
import traceback

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

for _mod_name in ("dt_paths", "dt_picker", "dt_progress", "dt_materials", "dt_spawn"):
    if _mod_name in sys.modules:
        importlib.reload(sys.modules[_mod_name])

import unreal

from dt_paths import (
    export_script_path,
    norm,
    pipeline_dir,
    plugin_python_dir,
    project_dir,
    output_run_dir,
)
from dt_picker import pick_media_files, show_message
from dt_progress import (
    ProgressPump,
    close_log,
    create_log_file,
    find_python_cmd,
    get_log_file_path,
    log_line,
    open_output_log,
)
from dt_spawn import spawn_scene_from_json

_ACTIVE_SESSION = None


def _on_preprocess_finished(pump: ProgressPump):
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
            "Viewport should look at the twin (not the sky).\n\nLog:\n{}".format(
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
        unreal.log_flush()
    except Exception:
        pass

    if _ACTIVE_SESSION is not None:
        show_message("Digital Twin", "Already running — check Output Log.")
        return

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

        log_line("[DigitalTwin] Plugin:  {}".format(plugin_py), log_file)
        log_line("[DigitalTwin] Pipeline: {}".format(pipe), log_file)
        log_line("[DigitalTwin] Export:   {}".format(export_py), log_file)
        log_line("[DigitalTwin] Project:  {}".format(project_dir()), log_file)
        log_line("[DigitalTwin] Output:   {}".format(out_dir), log_file)

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

        log_line("[DigitalTwin] Files: {}".format(len(abs_paths)), log_file)
        for p in abs_paths:
            log_line("  - {}".format(p), log_file)
        log_line("[DigitalTwin] Layout: from detections (any scene)", log_file)
        log_line("[DigitalTwin] Cmd: {}".format(subprocess.list2cmdline(argv)), log_file)
        log_line("[DigitalTwin] Preprocess RUNNING...", log_file)

        pump = ProgressPump(argv, pipe, log_file, out_dir, _on_preprocess_finished)
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
