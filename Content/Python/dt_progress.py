"""Output Log helpers + Packager-style preprocess progress pump."""

from __future__ import annotations

import datetime
import os
import queue
import subprocess
import threading

import unreal

from dt_paths import logs_dir, norm

_LOG_FILE_PATH = None


def get_log_file_path():
    return _LOG_FILE_PATH


def progress_bar(pct: int, width: int = 20) -> str:
    pct = max(0, min(100, int(pct)))
    filled = int(width * pct / 100)
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def open_output_log():
    try:
        sub = unreal.get_editor_subsystem(unreal.EditorUtilitySubsystem)
        if sub:
            sub.spawn_registered_tab_by_id("OutputLog")
    except Exception:
        pass
    unreal.log("=" * 72)
    unreal.log("Digital Twin Builder — live progress below")
    if _LOG_FILE_PATH:
        unreal.log("Log file: {}".format(_LOG_FILE_PATH))
    unreal.log("=" * 72)


def log_line(message: str, log_file=None):
    unreal.log(message)
    if log_file:
        try:
            log_file.write(message + "\n")
            log_file.flush()
        except Exception:
            pass
    try:
        unreal.log_flush()
    except Exception:
        pass


def create_log_file():
    global _LOG_FILE_PATH
    os.makedirs(logs_dir(), exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    _LOG_FILE_PATH = os.path.join(logs_dir(), "DigitalTwinBuilder_{}.log".format(stamp))
    handle = open(_LOG_FILE_PATH, "w", encoding="utf-8")
    log_line("Digital Twin Builder log: {}".format(_LOG_FILE_PATH), handle)
    return handle


def close_log(log_file):
    if log_file:
        try:
            log_file.close()
        except Exception:
            pass


def find_python_cmd() -> list:
    """Return argv prefix for system Python 3.12 (not UE embedded)."""
    for cmd in (["py", "-3.12"], ["python3"], ["python"]):
        try:
            r = subprocess.run(
                cmd + ["-c", "import sys; print(sys.version.split()[0])"],
                capture_output=True,
                text=True,
                timeout=20,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if r.returncode == 0:
                unreal.log(
                    "[DigitalTwin] Python: {} ({})".format(" ".join(cmd), r.stdout.strip())
                )
                return cmd
        except Exception:
            continue
    return ["py", "-3.12"]


class ProgressPump:
    STATUS_INTERVAL = 2.5

    def __init__(self, argv: list, cwd: str, log_file, out_dir: str, on_finished):
        self.argv = argv
        self.cwd = cwd
        self.log_file = log_file
        self.out_dir = out_dir
        self.on_finished = on_finished
        self.queue = queue.Queue()
        self.return_code = None
        self._done = threading.Event()
        self.last_line = ""
        self.progress_pct = 0
        self.scene_json = None
        self.ticker_handle = None
        self.elapsed = 0.0
        self.next_status_at = self.STATUS_INTERVAL
        self._finished_once = False

    def start(self):
        def _reader():
            try:
                creation = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                env = os.environ.copy()
                env["PYTHONIOENCODING"] = "utf-8"
                env["PYTHONUTF8"] = "1"
                process = subprocess.Popen(
                    self.argv,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    cwd=self.cwd,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    env=env,
                    creationflags=creation,
                )
                assert process.stdout is not None
                for line in process.stdout:
                    self.queue.put(line.rstrip("\n"))
                self.return_code = process.wait()
            except Exception as exc:
                self.queue.put("FAILED to start preprocess: {}".format(exc))
                self.return_code = 1
            finally:
                self._done.set()

        threading.Thread(target=_reader, daemon=True).start()
        self.ticker_handle = unreal.register_slate_post_tick_callback(self._on_tick)

    def pump(self, max_lines=500):
        n = 0
        while n < max_lines:
            try:
                line = self.queue.get_nowait()
            except queue.Empty:
                break
            n += 1
            self.last_line = line
            if line.startswith("PROGRESS:"):
                try:
                    body = line.split(":", 1)[1]
                    pct_s, msg = body.split("|", 1)
                    self.progress_pct = int(pct_s)
                    bar = progress_bar(self.progress_pct)
                    log_line(
                        "[DigitalTwin] {} {:>3}% — {}".format(bar, self.progress_pct, msg),
                        self.log_file,
                    )
                except Exception:
                    log_line(line, self.log_file)
            elif line.startswith("SCENE_JSON:"):
                self.scene_json = norm(line.split(":", 1)[1].strip().strip('"'))
                log_line(
                    "[DigitalTwin] Scene JSON ready: {}".format(self.scene_json),
                    self.log_file,
                )
            else:
                if line.strip():
                    log_line(line, self.log_file)

    def _unregister(self):
        if self.ticker_handle is not None:
            try:
                unreal.unregister_slate_post_tick_callback(self.ticker_handle)
            except Exception:
                pass
            self.ticker_handle = None

    def _on_tick(self, delta_time):
        self.elapsed += float(delta_time)
        self.pump()
        if self.elapsed >= self.next_status_at:
            self.next_status_at += self.STATUS_INTERVAL
            mins = int(self.elapsed // 60)
            secs = int(self.elapsed % 60)
            stage = self.last_line or "working..."
            if stage.startswith("PROGRESS:"):
                stage = stage.split("|", 1)[-1]
            if len(stage) > 80:
                stage = stage[:77] + "..."
            unreal.log(
                "[DigitalTwin] {:02d}:{:02d} {} {:>3}% — {}".format(
                    mins, secs, progress_bar(self.progress_pct), self.progress_pct, stage
                )
            )
            try:
                unreal.log_flush()
            except Exception:
                pass

        if self._done.is_set() and not self._finished_once:
            self.pump(max_lines=20000)
            if self.queue.empty():
                self._finished_once = True
                self._unregister()
                self.on_finished(self)
