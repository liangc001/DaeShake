"""Standalone Windows mouse-input diagnostic for DaeShake troubleshooting."""

from __future__ import annotations

import ctypes
import json
import os
import platform
import sys
import time
import tkinter as tk
from ctypes import wintypes


if sys.platform != "win32":
    raise RuntimeError("Windows only")

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_MOVE_NOCOALESCE = 0x2000
TOKEN_QUERY = 0x0008
TOKEN_ELEVATION_CLASS = 20


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ULONG_PTR),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("mi", MOUSEINPUT)]


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class TOKEN_ELEVATION(ctypes.Structure):
    _fields_ = [("TokenIsElevated", wintypes.DWORD)]


user32.SendInput.argtypes = [ctypes.c_uint, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = ctypes.c_uint
user32.mouse_event.argtypes = [ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ULONG_PTR]
user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
user32.GetCursorPos.restype = wintypes.BOOL
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.SetCursorPos.restype = wintypes.BOOL
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
kernel32.GetCurrentProcess.argtypes = []
kernel32.GetCurrentProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL
advapi32.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
advapi32.OpenProcessToken.restype = wintypes.BOOL
advapi32.GetTokenInformation.argtypes = [
    wintypes.HANDLE,
    ctypes.c_int,
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
]
advapi32.GetTokenInformation.restype = wintypes.BOOL


def elevated() -> bool | None:
    token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(kernel32.GetCurrentProcess(), TOKEN_QUERY, ctypes.byref(token)):
        return None
    try:
        value = TOKEN_ELEVATION()
        returned = wintypes.DWORD()
        if not advapi32.GetTokenInformation(
            token, TOKEN_ELEVATION_CLASS, ctypes.byref(value), ctypes.sizeof(value), ctypes.byref(returned)
        ):
            return None
        return bool(value.TokenIsElevated)
    finally:
        kernel32.CloseHandle(token)


def cursor() -> tuple[int, int]:
    point = POINT()
    if not user32.GetCursorPos(ctypes.byref(point)):
        raise ctypes.WinError(ctypes.get_last_error())
    return int(point.x), int(point.y)


def send_input_move(dx: int, dy: int) -> bool:
    event = INPUT()
    event.type = 0
    event.mi.dx = dx
    event.mi.dy = dy
    event.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_MOVE_NOCOALESCE
    return user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(INPUT)) == 1


def send_input_button(flags: int) -> bool:
    event = INPUT()
    event.type = 0
    event.mi.dwFlags = flags
    return user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(INPUT)) == 1


def legacy_move(dx: int, dy: int) -> bool:
    user32.mouse_event(MOUSEEVENTF_MOVE, dx, dy, 0, 0)
    return True


def legacy_button(flags: int) -> bool:
    user32.mouse_event(flags, 0, 0, 0, 0)
    return True


def run_test(root: tk.Tk, method: str, move, button) -> dict[str, object]:
    events: list[tuple[str, int, int]] = []
    window = tk.Toplevel(root)
    window.title("DaeShake input test - " + method)
    window.geometry("520x260+80+80")
    window.configure(bg="#ffffff")
    label = tk.Label(
        window,
        text="请不要移动鼠标\n正在测试 " + method,
        bg="#ffffff",
        font=("Arial", 16),
        width=35,
        height=8,
    )
    label.pack(fill="both", expand=True)
    label.bind("<ButtonPress-1>", lambda event: events.append(("down", event.x_root, event.y_root)))
    label.bind("<B1-Motion>", lambda event: events.append(("move", event.x_root, event.y_root)))
    label.bind("<ButtonRelease-1>", lambda event: events.append(("up", event.x_root, event.y_root)))
    root.update()
    window.update()
    window.focus_force()
    window.update()
    left, top = window.winfo_rootx(), window.winfo_rooty()
    start = (left + window.winfo_width() // 2, top + window.winfo_height() // 2)
    original = cursor()
    user32.SetCursorPos(*start)
    time.sleep(0.12)
    before = cursor()
    down_ok = bool(button(MOUSEEVENTF_LEFTDOWN))
    time.sleep(0.05)
    move_ok = 0
    for _ in range(12):
        move_ok += int(bool(move(6, 0)))
        root.update()
        time.sleep(0.015)
    time.sleep(0.08)
    up_ok = bool(button(MOUSEEVENTF_LEFTUP))
    root.update()
    time.sleep(0.15)
    after = cursor()
    result = {
        "method": method,
        "press_events": sum(event[0] == "down" for event in events),
        "motion_events": sum(event[0] == "move" for event in events),
        "release_events": sum(event[0] == "up" for event in events),
        "button_down_call_ok": down_ok,
        "move_call_ok_count": move_ok,
        "button_up_call_ok": up_ok,
        "cursor_before": before,
        "cursor_after": after,
        "cursor_delta": (after[0] - before[0], after[1] - before[1]),
        "left_button_still_down": bool(user32.GetAsyncKeyState(0x01) & 0x8000),
    }
    user32.SetCursorPos(*original)
    window.destroy()
    return result


def main() -> None:
    print("DaeShake input diagnostic")
    print("Do not move the mouse while the two tests run.")
    info_root = tk.Tk()
    info_root.withdraw()
    info = {
        "python": sys.version.split()[0],
        "system": platform.platform(),
        "machine": platform.machine(),
        "pointer_size": ctypes.sizeof(ctypes.c_void_p) * 8,
        "screen": (info_root.winfo_screenwidth(), info_root.winfo_screenheight()),
        "process_elevated": elevated(),
        "localappdata": os.environ.get("LOCALAPPDATA", ""),
    }
    print(json.dumps(info, ensure_ascii=False))
    root = info_root
    results = [
        run_test(root, "SendInput", send_input_move, send_input_button),
        run_test(root, "mouse_event", legacy_move, legacy_button),
    ]
    root.destroy()
    print(json.dumps({"results": results}, ensure_ascii=False))
    print("Copy all output above and send it back.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("DIAGNOSTIC_ERROR:", repr(error))
    finally:
        try:
            input("\n诊断结束。请复制上面的全部内容，然后按回车关闭窗口... ")
        except EOFError:
            pass
