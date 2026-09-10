"""Windows multi-select media picker + auto scene detection."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

import unreal

from dt_paths import norm

OFN_EXPLORER = 0x00080000
OFN_FILEMUSTEXIST = 0x00001000
OFN_PATHMUSTEXIST = 0x00000800
OFN_ALLOWMULTISELECT = 0x00000200
OFN_HIDEREADONLY = 0x00000004

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
VIDEO_EXT = {".mp4", ".mkv", ".mov", ".avi", ".wmv", ".m4v", ".webm"}


class OPENFILENAMEW(ctypes.Structure):
    _fields_ = [
        ("lStructSize", wintypes.DWORD),
        ("hwndOwner", wintypes.HWND),
        ("hInstance", wintypes.HINSTANCE),
        ("lpstrFilter", wintypes.LPCWSTR),
        ("lpstrCustomFilter", wintypes.LPWSTR),
        ("nMaxCustFilter", wintypes.DWORD),
        ("nFilterIndex", wintypes.DWORD),
        ("lpstrFile", wintypes.LPWSTR),
        ("nMaxFile", wintypes.DWORD),
        ("lpstrFileTitle", wintypes.LPWSTR),
        ("nMaxFileTitle", wintypes.DWORD),
        ("lpstrInitialDir", wintypes.LPCWSTR),
        ("lpstrTitle", wintypes.LPCWSTR),
        ("Flags", wintypes.DWORD),
        ("nFileOffset", wintypes.WORD),
        ("nFileExtension", wintypes.WORD),
        ("lpstrDefExt", wintypes.LPCWSTR),
        ("lCustData", wintypes.LPARAM),
        ("lpfnHook", ctypes.c_void_p),
        ("lpTemplateName", wintypes.LPCWSTR),
        ("pvReserved", ctypes.c_void_p),
        ("dwReserved", wintypes.DWORD),
        ("FlagsEx", wintypes.DWORD),
    ]


def _unicode_buffer_from_double_null(text: str):
    return ctypes.create_unicode_buffer(text)


def _read_double_null_paths(file_buffer, buffer_size: int):
    raw = ctypes.wstring_at(ctypes.addressof(file_buffer), buffer_size)
    parts = [p for p in raw.split("\0") if p]
    if not parts:
        return []
    if len(parts) == 1:
        return [norm(parts[0])]
    folder = parts[0]
    return [norm(os.path.join(folder, name)) for name in parts[1:]]


def pick_media_files():
    """Multi-select images and/or a video. Opens a Windows file dialog."""
    unreal.log("[DigitalTwin] Opening file picker (Ctrl+click for multiple images / video)...")
    try:
        unreal.log_flush()
    except Exception:
        pass

    buffer_size = 65536
    file_buffer = ctypes.create_unicode_buffer(buffer_size)
    filter_buffer = _unicode_buffer_from_double_null(
        "Media (images/video)\0*.jpg;*.jpeg;*.png;*.bmp;*.webp;*.mp4;*.mkv;*.mov;*.avi\0"
        "Images\0*.jpg;*.jpeg;*.png;*.bmp;*.webp\0"
        "Video\0*.mp4;*.mkv;*.mov;*.avi;*.wmv\0"
        "All Files\0*.*\0"
    )
    title_buffer = ctypes.create_unicode_buffer(
        "Select images and/or a video for the Digital Twin"
    )
    initial_buffer = ctypes.create_unicode_buffer(
        os.path.join(os.path.expanduser("~"), "Downloads")
    )

    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
    except Exception:
        hwnd = None

    ofn = OPENFILENAMEW()
    ofn.lStructSize = ctypes.sizeof(OPENFILENAMEW)
    ofn.hwndOwner = hwnd
    ofn.lpstrFilter = ctypes.cast(filter_buffer, wintypes.LPCWSTR)
    ofn.lpstrFile = ctypes.cast(file_buffer, wintypes.LPWSTR)
    ofn.nMaxFile = buffer_size
    ofn.lpstrTitle = ctypes.cast(title_buffer, wintypes.LPCWSTR)
    ofn.lpstrInitialDir = ctypes.cast(initial_buffer, wintypes.LPCWSTR)
    ofn.Flags = (
        OFN_EXPLORER
        | OFN_FILEMUSTEXIST
        | OFN_PATHMUSTEXIST
        | OFN_ALLOWMULTISELECT
        | OFN_HIDEREADONLY
    )

    get_open = ctypes.windll.comdlg32.GetOpenFileNameW
    get_open.argtypes = [ctypes.POINTER(OPENFILENAMEW)]
    get_open.restype = wintypes.BOOL
    if not get_open(ctypes.byref(ofn)):
        try:
            err = ctypes.windll.comdlg32.CommDlgExtendedError()
        except Exception:
            err = 0
        unreal.log("[DigitalTwin] File picker cancelled (CommDlgError={}).".format(err))
        return []

    paths = _read_double_null_paths(file_buffer, buffer_size)
    paths = [
        p
        for p in paths
        if os.path.isfile(p) and os.path.splitext(p)[1].lower() in (IMAGE_EXT | VIDEO_EXT)
    ]
    unreal.log("[DigitalTwin] Selected {} file(s)".format(len(paths)))
    for p in paths:
        unreal.log("  - {}".format(p))
    return paths


def show_message(title: str, message: str):
    if hasattr(unreal, "EditorDialog"):
        try:
            ok = getattr(getattr(unreal, "AppMsgType", object), "OK", None)
            if ok is not None:
                unreal.EditorDialog.show_message(title, message, ok)
                return
        except Exception:
            pass
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
    except Exception:
        hwnd = None
    ctypes.windll.user32.MessageBoxW(hwnd, message, title, 0)
