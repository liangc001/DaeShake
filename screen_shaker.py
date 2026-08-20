"""A Windows helper that simulates a short left-button drag in a target window."""

from __future__ import annotations

import ctypes
import json
import math
import os
from pathlib import Path
import sys
import threading
import time
import tkinter as tk
from dataclasses import dataclass
from ctypes import wintypes
from tkinter import ttk


if sys.platform != "win32":
    raise RuntimeError("screen_shaker.py only supports Windows.")


user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

HWND = ctypes.c_void_p
LPARAM = ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long
WPARAM = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong
ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
VK_F7 = 0x76
VK_F8 = 0x77
VK_F9 = 0x78
HOTKEY_LOCK = 1
HOTKEY_SHAKE = 2
HOTKEY_STOP = 3

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000
MOUSEEVENTF_MOVE_NOCOALESCE = 0x2000
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
TOKEN_QUERY = 0x0008
TOKEN_ELEVATION_CLASS = 20

SETTINGS_VERSION = 7
PRESET_OPTIONS = ("强力", "自定义")
INPUT_METHOD_OPTIONS = ("自动", "标准", "兼容")
PRESET_VALUES = {
    "强力": (200, 280),
}
STRATEGY_OPTIONS = (
    "水平往返",
    "垂直往返",
    "顺时针圆形",
    "逆时针圆形",
    "八字轨迹",
)
STRATEGY_ALIASES = {
    "水平": "水平往返",
    "垂直": "垂直往返",
}
DEFAULT_SETTINGS = {
    "distance": 200,
    "duration": 280,
    "preset": "强力",
    "cycles": 2,
    "direction": "水平往返",
    "origin": "顶部中心",
    "top_offset": 20,
    "input_method": "自动",
    "restore_cursor": True,
}
settings_root = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "DaeShake"
settings_file = settings_root / "settings.json"


def resource_path(name: str) -> Path:
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return bundle_root / name


def normalize_strategy(value: object) -> str:
    strategy = STRATEGY_ALIASES.get(str(value), str(value))
    if strategy not in STRATEGY_OPTIONS:
        return str(DEFAULT_SETTINGS["direction"])
    return strategy


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


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


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", HWND),
        ("message", ctypes.c_uint),
        ("wParam", WPARAM),
        ("lParam", LPARAM),
        ("time", ctypes.c_ulong),
        ("pt_x", ctypes.c_long),
        ("pt_y", ctypes.c_long),
        ("lPrivate", ctypes.c_ulong),
    ]


class TOKEN_ELEVATION(ctypes.Structure):
    _fields_ = [("TokenIsElevated", wintypes.DWORD)]


EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, HWND, LPARAM)

user32.EnumWindows.argtypes = [EnumWindowsProc, LPARAM]
user32.EnumWindows.restype = wintypes.BOOL
user32.IsWindow.argtypes = [HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.IsWindowEnabled.argtypes = [HWND]
user32.IsWindowEnabled.restype = wintypes.BOOL
user32.IsIconic.argtypes = [HWND]
user32.IsIconic.restype = wintypes.BOOL
user32.GetWindowTextLengthW.argtypes = [HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [HWND, ctypes.c_wchar_p, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetClientRect.argtypes = [HWND, ctypes.POINTER(RECT)]
user32.GetClientRect.restype = wintypes.BOOL
user32.ClientToScreen.argtypes = [HWND, ctypes.POINTER(POINT)]
user32.ClientToScreen.restype = wintypes.BOOL
user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = HWND
user32.SetForegroundWindow.argtypes = [HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
user32.GetCursorPos.restype = wintypes.BOOL
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.SetCursorPos.restype = wintypes.BOOL
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int
user32.SendInput.argtypes = [ctypes.c_uint, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = ctypes.c_uint
user32.mouse_event.argtypes = [ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ULONG_PTR]
user32.mouse_event.restype = None
user32.RegisterHotKey.argtypes = [HWND, ctypes.c_int, ctypes.c_uint, ctypes.c_uint]
user32.RegisterHotKey.restype = wintypes.BOOL
user32.UnregisterHotKey.argtypes = [HWND, ctypes.c_int]
user32.UnregisterHotKey.restype = wintypes.BOOL
user32.GetMessageW.argtypes = [ctypes.POINTER(MSG), HWND, ctypes.c_uint, ctypes.c_uint]
user32.GetMessageW.restype = ctypes.c_int
user32.PeekMessageW.argtypes = [ctypes.POINTER(MSG), HWND, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint]
user32.PeekMessageW.restype = wintypes.BOOL
user32.PostThreadMessageW.argtypes = [ctypes.c_uint, ctypes.c_uint, WPARAM, LPARAM]
user32.PostThreadMessageW.restype = wintypes.BOOL
user32.GetWindowThreadProcessId.argtypes = [HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
kernel32.GetCurrentThreadId.argtypes = []
kernel32.GetCurrentThreadId.restype = ctypes.c_uint
kernel32.GetCurrentProcess.argtypes = []
kernel32.GetCurrentProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
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


def hwnd_value(hwnd: HWND | int | None) -> int:
    value = getattr(hwnd, "value", hwnd)
    return int(value or 0)


def process_is_elevated(process_handle: wintypes.HANDLE) -> bool | None:
    token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(process_handle, TOKEN_QUERY, ctypes.byref(token)):
        return None
    try:
        elevation = TOKEN_ELEVATION()
        returned = wintypes.DWORD()
        if not advapi32.GetTokenInformation(
            token,
            TOKEN_ELEVATION_CLASS,
            ctypes.byref(elevation),
            ctypes.sizeof(elevation),
            ctypes.byref(returned),
        ):
            return None
        return bool(elevation.TokenIsElevated)
    finally:
        kernel32.CloseHandle(token)


def window_has_higher_privilege(hwnd: HWND | int) -> bool:
    process_id = wintypes.DWORD()
    if not user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id)) or not process_id.value:
        return False
    target_process = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, process_id.value)
    if not target_process:
        return False
    try:
        target_elevated = process_is_elevated(target_process)
        current_elevated = process_is_elevated(kernel32.GetCurrentProcess())
        return target_elevated is True and current_elevated is False
    finally:
        kernel32.CloseHandle(target_process)


@dataclass(frozen=True)
class WindowItem:
    hwnd: int
    title: str

    @property
    def display(self) -> str:
        return f"{self.title}  [0x{self.hwnd:X}]"


def set_process_dpi_aware() -> None:
    """Keep Win32 client coordinates aligned with the physical desktop."""

    try:
        shcore = ctypes.WinDLL("shcore", use_last_error=True)
        shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            user32.SetProcessDPIAware()
        except AttributeError:
            pass


def get_window_title(hwnd: HWND | int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, len(buffer))
    return buffer.value.strip()


def enumerate_windows(excluded_hwnd: int | None = None) -> list[WindowItem]:
    windows: list[WindowItem] = []

    @EnumWindowsProc
    def callback(hwnd: HWND, _lparam: LPARAM) -> bool:
        value = hwnd_value(hwnd)
        if value == 0 or value == excluded_hwnd:
            return True
        if not user32.IsWindowVisible(hwnd):
            return True
        title = get_window_title(hwnd)
        if title:
            windows.append(WindowItem(value, title))
        return True

    user32.EnumWindows(callback, 0)
    return sorted(windows, key=lambda item: item.title.casefold())


def send_mouse_button(flags: int) -> bool:
    event = INPUT()
    event.type = 0  # INPUT_MOUSE
    event.mi.dwFlags = flags
    return user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(INPUT)) == 1


def virtual_screen_bounds() -> tuple[int, int, int, int]:
    """Return the physical-coordinate bounds used by absolute mouse input."""

    left = int(user32.GetSystemMetrics(SM_XVIRTUALSCREEN))
    top = int(user32.GetSystemMetrics(SM_YVIRTUALSCREEN))
    width = max(1, int(user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)))
    height = max(1, int(user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)))
    return left, top, width, height


def normalize_absolute_point(x: int, y: int) -> tuple[int, int]:
    left, top, width, height = virtual_screen_bounds()
    normalized_x = round((int(x) - left) * 65535 / max(1, width - 1))
    normalized_y = round((int(y) - top) * 65535 / max(1, height - 1))
    return min(65535, max(0, normalized_x)), min(65535, max(0, normalized_y))


def send_mouse_move_absolute(x: int, y: int) -> bool:
    normalized_x, normalized_y = normalize_absolute_point(x, y)
    event = INPUT()
    event.type = 0  # INPUT_MOUSE
    event.mi.dx = normalized_x
    event.mi.dy = normalized_y
    event.mi.dwFlags = (
        MOUSEEVENTF_MOVE
        | MOUSEEVENTF_ABSOLUTE
        | MOUSEEVENTF_VIRTUALDESK
        | MOUSEEVENTF_MOVE_NOCOALESCE
    )
    return user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(INPUT)) == 1


def send_mouse_move_legacy_absolute(x: int, y: int) -> bool:
    normalized_x, normalized_y = normalize_absolute_point(x, y)
    user32.mouse_event(
        MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK,
        normalized_x,
        normalized_y,
        0,
        0,
    )
    return True


def send_mouse_button_legacy(flags: int) -> bool:
    user32.mouse_event(flags, 0, 0, 0, 0)
    return True


def normalize_cycles(value: object) -> int:
    try:
        cycles = int(value)
    except (TypeError, ValueError):
        cycles = int(DEFAULT_SETTINGS["cycles"])
    cycles = min(8, max(2, cycles))
    if cycles % 2:
        cycles = min(8, cycles + 1)
    return cycles


def load_settings() -> dict[str, object]:
    settings = dict(DEFAULT_SETTINGS)
    saved_version = 0
    try:
        saved = json.loads(settings_file.read_text(encoding="utf-8"))
        if isinstance(saved, dict):
            try:
                saved_version = int(saved.get("version", 0))
            except (TypeError, ValueError):
                saved_version = 0
            for key in DEFAULT_SETTINGS:
                if key in saved:
                    settings[key] = saved[key]
    except (OSError, ValueError, TypeError):
        pass
    try:
        settings["distance"] = min(300, max(4, int(float(settings["distance"]))))
    except (TypeError, ValueError):
        settings["distance"] = DEFAULT_SETTINGS["distance"]
    try:
        settings["duration"] = min(1200, max(120, int(float(settings["duration"]))))
    except (TypeError, ValueError):
        settings["duration"] = DEFAULT_SETTINGS["duration"]
    settings["cycles"] = normalize_cycles(settings["cycles"])
    if settings["preset"] not in PRESET_OPTIONS:
        settings["preset"] = "自定义"
    if settings["input_method"] not in INPUT_METHOD_OPTIONS:
        settings["input_method"] = DEFAULT_SETTINGS["input_method"]
    try:
        settings["top_offset"] = min(160, max(0, int(float(settings["top_offset"]))))
    except (TypeError, ValueError):
        settings["top_offset"] = DEFAULT_SETTINGS["top_offset"]
    settings["direction"] = normalize_strategy(settings["direction"])
    if settings["origin"] not in ("顶部中心", "客户区中心", "当前鼠标"):
        settings["origin"] = DEFAULT_SETTINGS["origin"]
    settings["restore_cursor"] = bool(settings["restore_cursor"])
    if saved_version < 4:
        settings["origin"] = DEFAULT_SETTINGS["origin"]
        settings["top_offset"] = DEFAULT_SETTINGS["top_offset"]
        settings["cycles"] = DEFAULT_SETTINGS["cycles"]
    if saved_version < SETTINGS_VERSION and settings["distance"] == 100:
        settings["distance"] = DEFAULT_SETTINGS["distance"]
    preset_values = PRESET_VALUES.get(str(settings["preset"]))
    if preset_values != (settings["distance"], settings["duration"]):
        settings["preset"] = "自定义"
    return settings


class ShakeApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("抓大鹅 - 晃屏助手")
        self.root.configure(bg="#f3f6f8")
        try:
            self.root.iconbitmap(default=str(resource_path("app_icon.ico")))
        except (OSError, tk.TclError):
            pass
        self.configure_window_size()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.window_items: list[WindowItem] = []
        self.target_hwnd: int | None = None
        self.target_title = ""
        self.dragging = False
        self.drag_pressed = False
        self.drag_original_cursor: tuple[int, int] | None = None
        self.drag_points: list[tuple[int, int]] = []
        self.drag_index = 0
        self.drag_duration = 0
        self.drag_started_at = 0.0
        self.drag_watchdog_id: str | None = None
        self.active_input_mode: str | None = None
        self.applying_preset = False
        self.vertical_lane_index = 0
        self.stop_hotkeys = threading.Event()
        self.hotkey_thread: threading.Thread | None = None
        self.hotkey_thread_id: int | None = None
        self.save_job_id: str | None = None
        self.header_icon_source: tk.PhotoImage | None = None
        self.header_icon: tk.PhotoImage | None = None
        self.ui_icons: dict[str, tk.PhotoImage] = {}

        settings = load_settings()
        self.window_var = tk.StringVar()
        self.target_var = tk.StringVar(value="尚未锁定目标窗口")
        self.status_var = tk.StringVar(value="准备就绪")
        self.distance_var = tk.DoubleVar(value=float(settings["distance"]))
        self.duration_var = tk.DoubleVar(value=float(settings["duration"]))
        self.preset_var = tk.StringVar(value=str(settings["preset"]))
        self.cycles_var = tk.StringVar(value=str(settings["cycles"]))
        self.direction_var = tk.StringVar(value=str(settings["direction"]))
        self.origin_var = tk.StringVar(value=str(settings["origin"]))
        self.top_offset_var = tk.DoubleVar(value=float(settings["top_offset"]))
        self.input_method_var = tk.StringVar(value=str(settings["input_method"]))
        self.restore_cursor_var = tk.BooleanVar(value=bool(settings["restore_cursor"]))
        self.distance_label_var = tk.StringVar(value=f"{round(self.distance_var.get())} px")
        self.duration_label_var = tk.StringVar(value=f"{round(self.duration_var.get())} ms")
        self.speed_label_var = tk.StringVar()
        self.top_offset_label_var = tk.StringVar(value=f"{round(self.top_offset_var.get())} px")

        self.configure_style()
        self.build_ui()
        self.auto_find_goose(silent=True)
        self.root.after_idle(lambda: self.scroll_canvas.yview_moveto(0.0))
        self.start_hotkeys()

    def configure_window_size(self) -> None:
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        width = min(620, max(360, screen_width - 32))
        height = min(740, max(420, screen_height - 72))
        self.root.geometry(f"{width}x{height}")
        self.root.minsize(min(360, width), min(420, height))
        self.root.resizable(True, True)

    def configure_style(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass
        style.configure("TFrame", background="#f3f6f8")
        style.configure("Panel.TFrame", background="#ffffff")
        style.configure("TLabel", background="#f3f6f8", foreground="#243b53", font=("Microsoft YaHei UI", 10))
        style.configure("Panel.TLabel", background="#ffffff", foreground="#243b53", font=("Microsoft YaHei UI", 10))
        style.configure("Title.TLabel", background="#f3f6f8", foreground="#17324d", font=("Microsoft YaHei UI", 19, "bold"))
        style.configure("Subtitle.TLabel", background="#f3f6f8", foreground="#607286", font=("Microsoft YaHei UI", 9))
        style.configure("Section.TLabel", background="#ffffff", foreground="#0f766e", font=("Microsoft YaHei UI", 11, "bold"))
        style.configure("Hint.TLabel", background="#ffffff", foreground="#66788a", font=("Microsoft YaHei UI", 9))
        style.configure("Panel.TCheckbutton", background="#ffffff", foreground="#243b53", font=("Microsoft YaHei UI", 9))
        style.configure("Gift.TLabel", background="#f3f6f8", foreground="#718096", font=("Microsoft YaHei UI", 9))
        style.configure("Metric.TLabel", background="#ffffff", foreground="#0f766e", font=("Microsoft YaHei UI", 9, "bold"))
        style.configure("Small.TButton", font=("Microsoft YaHei UI", 9), padding=(9, 5))
        style.configure("TCombobox", padding=5)

    def load_ui_icons(self) -> None:
        for name in (
            "target",
            "sliders",
            "refresh",
            "search",
            "check",
            "play_white",
            "stop_white",
            "gift",
        ):
            try:
                self.ui_icons[name] = tk.PhotoImage(file=str(resource_path(f"ui_icons/{name}.png")))
            except tk.TclError:
                pass

    def add_section_heading(self, parent: tk.Misc, text: str, icon_name: str) -> None:
        row = tk.Frame(parent, bg="#ffffff")
        row.pack(anchor="w")
        icon = self.ui_icons.get(icon_name)
        if icon is not None:
            tk.Label(row, image=icon, bg="#ffffff", borderwidth=0).pack(side="left", padx=(0, 8))
        ttk.Label(row, text=text, style="Section.TLabel").pack(side="left")

    def build_ui(self) -> None:
        self.load_ui_icons()
        viewport = tk.Frame(self.root, bg="#f3f6f8", borderwidth=0, highlightthickness=0)
        viewport.pack(fill="both", expand=True)
        canvas = tk.Canvas(viewport, bg="#f3f6f8", borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(viewport, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        outer = ttk.Frame(canvas, padding=(16, 20, 16, 16))
        outer_window = canvas.create_window((0, 0), window=outer, anchor="nw")
        self.scroll_canvas = canvas
        self.wrap_labels: list[tk.Misc] = []

        outer.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        def resize_outer(event: tk.Event) -> None:
            canvas.itemconfigure(outer_window, width=event.width)
            self.update_wrap_lengths()

        canvas.bind("<Configure>", resize_outer)
        self.root.bind_all("<MouseWheel>", self.on_mousewheel, add="+")
        self.root.bind("<Configure>", self.update_wrap_lengths, add="+")

        header = tk.Frame(
            outer,
            bg="#163b45",
            padx=16,
            pady=14,
            borderwidth=0,
            highlightthickness=0,
        )
        header.pack(fill="x", pady=(0, 16))
        header_row = tk.Frame(header, bg="#163b45")
        header_row.pack(fill="x")
        try:
            self.header_icon_source = tk.PhotoImage(file=str(resource_path("app_icon.png")))
            self.header_icon = self.header_icon_source.subsample(32, 32)
        except tk.TclError:
            self.header_icon_source = None
            self.header_icon = None
        if self.header_icon is not None:
            tk.Label(header_row, image=self.header_icon, bg="#163b45", borderwidth=0).pack(
                side="left", padx=(0, 10)
            )
        tk.Label(
            header_row,
            text="抓大鹅 · 晃屏助手",
            bg="#163b45",
            fg="#ffffff",
            font=("Microsoft YaHei UI", 17, "bold"),
        ).pack(side="left")
        header_hint = tk.Label(
            header,
            text="保持抓大鹅小程序在前台，按 Ctrl+Alt+F8 晃一下",
            bg="#163b45",
            fg="#c8dfe2",
            font=("Microsoft YaHei UI", 9),
            anchor="w",
            justify="left",
        )
        header_hint.pack(fill="x", pady=(9, 0))
        self.wrap_labels.append(header_hint)

        target_panel = tk.Frame(
            outer,
            bg="#ffffff",
            padx=12,
            pady=12,
            borderwidth=0,
            relief="flat",
            highlightbackground="#d7e3e8",
            highlightcolor="#d7e3e8",
            highlightthickness=1,
        )
        target_panel.pack(fill="x")
        self.add_section_heading(target_panel, "目标窗口", "target")
        target_hint_label = ttk.Label(
            target_panel,
            text="默认从客户区顶部中心开始，按住左键连续拖动。",
            style="Hint.TLabel",
        )
        target_hint_label.pack(anchor="w", pady=(3, 10))
        self.wrap_labels.append(target_hint_label)

        select_row = ttk.Frame(target_panel, style="Panel.TFrame")
        select_row.pack(fill="x")
        self.window_combo = ttk.Combobox(
            select_row,
            textvariable=self.window_var,
            state="readonly",
            height=12,
            width=8,
        )
        self.window_combo.pack(side="left", fill="x", expand=True)

        target_actions = ttk.Frame(target_panel, style="Panel.TFrame")
        target_actions.pack(fill="x", pady=(8, 0))
        target_actions.columnconfigure(0, weight=1)
        target_actions.columnconfigure(1, weight=1)
        ttk.Button(
            target_actions,
            text="刷新",
            image=self.ui_icons.get("refresh"),
            compound="left",
            style="Small.TButton",
            command=self.refresh_windows,
        ).grid(
            row=0, column=0, sticky="ew"
        )
        ttk.Button(
            target_actions,
            text="自动找抓大鹅",
            image=self.ui_icons.get("search"),
            compound="left",
            style="Small.TButton",
            command=self.auto_find_goose,
        ).grid(
            row=0, column=1, sticky="ew", padx=(8, 0)
        )
        ttk.Button(
            target_actions,
            text="设为目标",
            image=self.ui_icons.get("check"),
            compound="left",
            style="Small.TButton",
            command=self.set_target,
        ).grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0)
        )

        target_label = ttk.Label(target_panel, textvariable=self.target_var, style="Hint.TLabel")
        target_label.pack(anchor="w", pady=(10, 0))
        self.wrap_labels.append(target_label)

        settings_panel = tk.Frame(
            outer,
            bg="#ffffff",
            padx=12,
            pady=12,
            borderwidth=0,
            relief="flat",
            highlightbackground="#d7e3e8",
            highlightcolor="#d7e3e8",
            highlightthickness=1,
        )
        settings_panel.pack(fill="x", pady=(14, 0))
        self.add_section_heading(settings_panel, "拖动参数", "sliders")

        preset_row = tk.Frame(settings_panel, bg="#ffffff")
        preset_row.pack(fill="x", pady=(12, 2))
        ttk.Label(preset_row, text="模式", style="Panel.TLabel", width=9).pack(side="left")
        preset_control = tk.Frame(preset_row, bg="#e8eef1", padx=2, pady=2)
        preset_control.pack(side="left", fill="x", expand=True, padx=(4, 0))
        for preset in PRESET_OPTIONS:
            tk.Radiobutton(
                preset_control,
                text=preset,
                value=preset,
                variable=self.preset_var,
                command=self.apply_preset,
                indicatoron=False,
                bg="#e8eef1",
                fg="#40566b",
                selectcolor="#b9dcd8",
                activebackground="#d7e7e7",
                activeforeground="#17324d",
                font=("Microsoft YaHei UI", 9, "bold"),
                relief="flat",
                borderwidth=0,
                padx=8,
                pady=5,
                cursor="hand2",
            ).pack(side="left", fill="x", expand=True)

        distance_row = ttk.Frame(settings_panel, style="Panel.TFrame")
        distance_row.pack(fill="x", pady=(10, 0))
        ttk.Label(distance_row, text="拖动距离", style="Panel.TLabel", width=9).pack(side="left")
        distance_scale = ttk.Scale(
            distance_row,
            from_=4,
            to=300,
            variable=self.distance_var,
            command=self.update_distance_label,
        )
        distance_scale.pack(side="left", fill="x", expand=True, padx=(4, 12))
        ttk.Label(distance_row, textvariable=self.distance_label_var, style="Panel.TLabel", width=7).pack(side="left")

        duration_row = ttk.Frame(settings_panel, style="Panel.TFrame")
        duration_row.pack(fill="x", pady=(10, 0))
        ttk.Label(duration_row, text="持续时间", style="Panel.TLabel", width=9).pack(side="left")
        duration_scale = ttk.Scale(
            duration_row,
            from_=120,
            to=1200,
            variable=self.duration_var,
            command=self.update_duration_label,
        )
        duration_scale.pack(side="left", fill="x", expand=True, padx=(4, 12))
        ttk.Label(duration_row, textvariable=self.duration_label_var, style="Panel.TLabel", width=7).pack(side="left")
        ttk.Label(settings_panel, textvariable=self.speed_label_var, style="Metric.TLabel").pack(
            anchor="e", pady=(4, 0)
        )

        cycles_row = ttk.Frame(settings_panel, style="Panel.TFrame")
        cycles_row.pack(fill="x", pady=(10, 0))
        ttk.Label(cycles_row, text="重复次数", style="Panel.TLabel", width=9).pack(side="left")
        self.cycles_combo = ttk.Combobox(
            cycles_row,
            values=("2", "4", "6", "8"),
            state="readonly",
            width=5,
            textvariable=self.cycles_var,
        )
        self.cycles_combo.pack(side="left", padx=(4, 0))
        self.cycles_combo.bind("<<ComboboxSelected>>", self.on_shape_option_changed)

        direction_row = ttk.Frame(settings_panel, style="Panel.TFrame")
        direction_row.pack(fill="x", pady=(10, 0))
        ttk.Label(direction_row, text="摇晃策略", style="Panel.TLabel", width=9).pack(side="left")
        self.direction_combo = ttk.Combobox(
            direction_row,
            textvariable=self.direction_var,
            values=STRATEGY_OPTIONS,
            state="readonly",
            width=14,
        )
        self.direction_combo.pack(side="left", padx=(4, 0))
        self.direction_combo.bind("<<ComboboxSelected>>", self.on_shape_option_changed)

        origin_row = ttk.Frame(settings_panel, style="Panel.TFrame")
        origin_row.pack(fill="x", pady=(10, 0))
        ttk.Label(origin_row, text="起点", style="Panel.TLabel", width=9).pack(side="left")
        self.origin_combo = ttk.Combobox(
            origin_row,
            textvariable=self.origin_var,
            values=("顶部中心", "客户区中心", "当前鼠标"),
            state="readonly",
            width=12,
        )
        self.origin_combo.pack(side="left", padx=(4, 0))
        self.origin_combo.bind("<<ComboboxSelected>>", lambda _event: self.schedule_save())

        top_offset_row = ttk.Frame(settings_panel, style="Panel.TFrame")
        top_offset_row.pack(fill="x", pady=(10, 0))
        ttk.Label(top_offset_row, text="顶部偏移", style="Panel.TLabel", width=9).pack(side="left")
        top_offset_scale = ttk.Scale(
            top_offset_row,
            from_=0,
            to=160,
            variable=self.top_offset_var,
            command=self.update_top_offset_label,
        )
        top_offset_scale.pack(side="left", fill="x", expand=True, padx=(4, 12))
        ttk.Label(top_offset_row, textvariable=self.top_offset_label_var, style="Panel.TLabel", width=7).pack(side="left")

        input_method_row = ttk.Frame(settings_panel, style="Panel.TFrame")
        input_method_row.pack(fill="x", pady=(10, 0))
        ttk.Label(input_method_row, text="输入方式", style="Panel.TLabel", width=9).pack(side="left")
        self.input_method_combo = ttk.Combobox(
            input_method_row,
            textvariable=self.input_method_var,
            values=INPUT_METHOD_OPTIONS,
            state="readonly",
            width=12,
        )
        self.input_method_combo.pack(side="left", padx=(4, 0))
        self.input_method_combo.bind("<<ComboboxSelected>>", self.on_input_method_changed)

        ttk.Checkbutton(
            settings_panel,
            text="完成后恢复鼠标位置",
            variable=self.restore_cursor_var,
            command=self.schedule_save,
            style="Panel.TCheckbutton",
        ).pack(anchor="w", pady=(10, 0))

        button_row = ttk.Frame(outer)
        button_row.pack(fill="x", pady=(18, 12))
        button_row.columnconfigure(0, weight=1)
        button_row.columnconfigure(1, weight=0, minsize=118)
        button_row.rowconfigure(0, minsize=58)
        self.shake_button = tk.Button(
            button_row,
            text="晃一下",
            image=self.ui_icons.get("play_white"),
            compound="left",
            command=self.quick_shake,
            font=("Microsoft YaHei UI", 15, "bold"),
            bg="#0f766e",
            fg="#ffffff",
            activebackground="#0b5d58",
            activeforeground="#ffffff",
            relief="flat",
            borderwidth=0,
            cursor="hand2",
            padx=18,
            pady=12,
        )
        self.shake_button.grid(row=0, column=0, sticky="nsew")
        self.stop_button = tk.Button(
            button_row,
            text="停止",
            image=self.ui_icons.get("stop_white"),
            compound="left",
            command=self.stop_drag,
            font=("Microsoft YaHei UI", 11, "bold"),
            bg="#9f4450",
            fg="#ffffff",
            activebackground="#923c46",
            activeforeground="#ffffff",
            relief="flat",
            borderwidth=0,
            cursor="hand2",
            padx=16,
            pady=12,
            state="disabled",
        )
        self.stop_button.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        shortcut_label = ttk.Label(
            outer,
            text="Ctrl+Alt+F7 锁定    Ctrl+Alt+F8 晃一下    Ctrl+Alt+F9 急停",
            style="Subtitle.TLabel",
        )
        shortcut_label.pack(anchor="w")
        self.wrap_labels.append(shortcut_label)
        status_label = ttk.Label(outer, textvariable=self.status_var, style="Subtitle.TLabel")
        status_label.pack(anchor="w", pady=(6, 0))
        self.wrap_labels.append(status_label)
        gift_row = tk.Frame(outer, bg="#f3f6f8")
        gift_row.pack(anchor="e", pady=(12, 0))
        gift_icon = self.ui_icons.get("gift")
        if gift_icon is not None:
            tk.Label(gift_row, image=gift_icon, bg="#f3f6f8", borderwidth=0).pack(side="left", padx=(0, 5))
        ttk.Label(gift_row, text="送给s的七夕礼物。", style="Gift.TLabel").pack(side="left")
        self.update_speed_label()
        self.update_wrap_lengths()

    def update_wrap_lengths(self, _event: tk.Event | None = None) -> None:
        wraplength = max(180, self.root.winfo_width() - 100)
        for label in self.wrap_labels:
            label.configure(wraplength=wraplength)

    def on_mousewheel(self, event: tk.Event) -> None:
        if event.delta:
            direction = -1 if event.delta > 0 else 1
            self.scroll_canvas.yview_scroll(direction, "units")

    def update_distance_label(self, value: str) -> None:
        self.distance_label_var.set(f"{round(float(value))} px")
        self.mark_custom_preset()
        self.update_speed_label()
        self.schedule_save()

    def update_duration_label(self, value: str) -> None:
        self.duration_label_var.set(f"{round(float(value))} ms")
        self.mark_custom_preset()
        self.update_speed_label()
        self.schedule_save()

    def apply_preset(self) -> None:
        values = PRESET_VALUES.get(self.preset_var.get())
        if values is None:
            self.schedule_save()
            return
        self.applying_preset = True
        distance, duration = values
        self.distance_var.set(distance)
        self.duration_var.set(duration)
        self.distance_label_var.set(f"{distance} px")
        self.duration_label_var.set(f"{duration} ms")
        self.applying_preset = False
        self.update_speed_label()
        self.schedule_save()

    def mark_custom_preset(self) -> None:
        if not self.applying_preset:
            self.preset_var.set("自定义")

    def on_shape_option_changed(self, _event: tk.Event | None = None) -> None:
        self.update_speed_label()
        self.schedule_save()

    def on_input_method_changed(self, _event: tk.Event | None = None) -> None:
        self.active_input_mode = None
        self.schedule_save()

    def update_speed_label(self) -> None:
        try:
            distance = round(float(self.distance_var.get()))
            duration = max(1, round(float(self.duration_var.get())))
            cycles = normalize_cycles(self.cycles_var.get())
            strategy = normalize_strategy(self.direction_var.get())
            points = self.build_drag_points(0, 0, distance, cycles, strategy, duration)
            path_length = sum(
                math.hypot(points[index][0] - points[index - 1][0], points[index][1] - points[index - 1][1])
                for index in range(1, len(points))
            )
            speed = round(path_length * 1000.0 / duration)
            self.speed_label_var.set(f"预计平均速度  {speed:,} px/s")
        except (tk.TclError, TypeError, ValueError):
            self.speed_label_var.set("预计平均速度  --")

    def update_top_offset_label(self, value: str) -> None:
        self.top_offset_label_var.set(f"{round(float(value))} px")
        self.schedule_save()

    def schedule_save(self) -> None:
        if self.save_job_id is not None:
            try:
                self.root.after_cancel(self.save_job_id)
            except tk.TclError:
                pass
        try:
            self.save_job_id = self.root.after(250, self.save_settings)
        except tk.TclError:
            self.save_job_id = None

    def get_settings(self) -> dict[str, object]:
        try:
            distance = round(float(self.distance_var.get()))
        except (tk.TclError, TypeError, ValueError):
            distance = int(DEFAULT_SETTINGS["distance"])
        try:
            duration = round(float(self.duration_var.get()))
        except (tk.TclError, TypeError, ValueError):
            duration = int(DEFAULT_SETTINGS["duration"])
        try:
            cycles = normalize_cycles(self.cycles_var.get())
        except (tk.TclError, TypeError, ValueError):
            cycles = int(DEFAULT_SETTINGS["cycles"])
        try:
            top_offset = round(float(self.top_offset_var.get()))
        except (tk.TclError, TypeError, ValueError):
            top_offset = int(DEFAULT_SETTINGS["top_offset"])

        return {
            "distance": min(300, max(4, distance)),
            "duration": min(1200, max(120, duration)),
            "preset": self.preset_var.get() if self.preset_var.get() in PRESET_OPTIONS else "自定义",
            "cycles": normalize_cycles(cycles),
            "direction": normalize_strategy(self.direction_var.get()),
            "origin": self.origin_var.get() if self.origin_var.get() in ("顶部中心", "客户区中心", "当前鼠标") else "顶部中心",
            "top_offset": min(160, max(0, top_offset)),
            "input_method": (
                self.input_method_var.get()
                if self.input_method_var.get() in INPUT_METHOD_OPTIONS
                else DEFAULT_SETTINGS["input_method"]
            ),
            "restore_cursor": bool(self.restore_cursor_var.get()),
            "version": SETTINGS_VERSION,
        }

    def save_settings(self) -> None:
        self.save_job_id = None
        try:
            settings_root.mkdir(parents=True, exist_ok=True)
            settings_file.write_text(
                json.dumps(self.get_settings(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            self.status_var.set("设置无法保存，但当前运行不受影响")

    def refresh_windows(self) -> None:
        previous_target = self.target_hwnd
        self.window_items = enumerate_windows(excluded_hwnd=self.root.winfo_id())
        values = [item.display for item in self.window_items]
        self.window_combo["values"] = values

        target_index = next(
            (index for index, item in enumerate(self.window_items) if item.hwnd == previous_target),
            None,
        )
        if target_index is not None:
            self.window_combo.current(target_index)
        elif values:
            self.window_combo.current(0)
            if previous_target is not None:
                self.target_hwnd = None
                self.target_title = ""
                self.target_var.set("原目标窗口已不存在，请重新设为目标")
        else:
            self.window_var.set("")
            self.target_var.set("没有找到可用的可见窗口")

        self.status_var.set(f"已发现 {len(values)} 个可见窗口")

    def use_target_item(self, item: WindowItem, status: str = "目标已锁定") -> None:
        self.target_hwnd = item.hwnd
        self.target_title = item.title
        self.target_var.set(f"已锁定：{item.title}")
        self.status_var.set(status)
        for index, candidate in enumerate(self.window_items):
            if candidate.hwnd == item.hwnd:
                self.window_combo.current(index)
                break

    def auto_find_goose(self, silent: bool = False) -> bool:
        self.refresh_windows()
        candidates = [
            item
            for item in self.window_items
            if "抓大鹅" in item.title.replace(" ", "")
        ]
        if not candidates:
            if not silent:
                self.status_var.set("没有找到“抓大鹅”窗口，请先打开对应小程序")
            return False
        self.use_target_item(candidates[0], "已自动找到抓大鹅窗口")
        return True

    def set_target(self) -> None:
        index = self.window_combo.current()
        if index < 0 or index >= len(self.window_items):
            self.status_var.set("请先从列表选择一个窗口")
            return

        self.use_target_item(self.window_items[index])

    def lock_foreground_window(self) -> None:
        hwnd = hwnd_value(user32.GetForegroundWindow())
        if not hwnd or hwnd == self.root.winfo_id():
            self.status_var.set("锁定失败：当前前台窗口是本工具")
            return

        title = get_window_title(hwnd)
        if not title or not user32.IsWindowVisible(hwnd):
            self.status_var.set("锁定失败：当前前台窗口不可用")
            return

        self.use_target_item(WindowItem(hwnd, title), "已锁定当前前台窗口")

    def quick_shake(self) -> None:
        if not self.target_hwnd or not user32.IsWindow(self.target_hwnd):
            if not self.auto_find_goose():
                return
        self.shake_target()

    def shake_from_hotkey(self) -> None:
        foreground = hwnd_value(user32.GetForegroundWindow())
        if foreground and foreground != self.root.winfo_id():
            title = get_window_title(foreground)
            if title and user32.IsWindowVisible(foreground):
                self.use_target_item(WindowItem(foreground, title), "已使用当前前台窗口")
        self.quick_shake()

    def get_client_bounds(self, hwnd: int) -> tuple[int, int, int, int] | None:
        rect = RECT()
        if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
            return None
        width = rect.right - rect.left
        height = rect.bottom - rect.top
        if width < 80 or height < 80:
            return None

        top_left = POINT(0, 0)
        bottom_right = POINT(width, height)
        if not user32.ClientToScreen(hwnd, ctypes.byref(top_left)):
            return None
        if not user32.ClientToScreen(hwnd, ctypes.byref(bottom_right)):
            return None
        return int(top_left.x), int(top_left.y), int(bottom_right.x), int(bottom_right.y)

    def get_drag_start(
        self,
        bounds: tuple[int, int, int, int],
        distance: int,
        direction: str,
        top_offset: int,
    ) -> tuple[int, int]:
        left, top, right, bottom = bounds
        strategy = normalize_strategy(direction)
        if self.origin_var.get() == "当前鼠标":
            cursor = POINT()
            if user32.GetCursorPos(ctypes.byref(cursor)):
                start_x, start_y = int(cursor.x), int(cursor.y)
                if left <= start_x <= right and top <= start_y <= bottom:
                    return self.clamp_drag_start(start_x, start_y, bounds, distance, strategy)

        center_x = left + (right - left) // 2
        if self.origin_var.get() == "顶部中心":
            # Vertical shaking needs room above and below the center point.
            # Move its center down so the upward leg stays below the toolbar.
            center_y = top + top_offset + (distance if strategy != "水平往返" else 0)
        else:
            center_y = top + (bottom - top) // 2
        return self.clamp_drag_start(center_x, center_y, bounds, distance, strategy)

    @staticmethod
    def clamp_drag_start(
        start_x: int,
        start_y: int,
        bounds: tuple[int, int, int, int],
        distance: int,
        direction: str,
    ) -> tuple[int, int]:
        left, top, right, bottom = bounds
        strategy = normalize_strategy(direction)
        x_margin = distance + 4 if strategy != "垂直往返" else 4
        y_margin = distance + 4 if strategy != "水平往返" else 4
        min_x, max_x = left + x_margin, right - x_margin
        min_y, max_y = top + y_margin, bottom - y_margin
        if min_x > max_x:
            start_x = left + (right - left) // 2
        else:
            start_x = min(max(start_x, min_x), max_x)
        if min_y > max_y:
            start_y = top + (bottom - top) // 2
        else:
            start_y = min(max(start_y, min_y), max_y)
        return start_x, start_y

    @staticmethod
    def fit_distance_to_bounds(
        bounds: tuple[int, int, int, int],
        requested_distance: int,
        direction: str,
        origin: str,
        top_offset: int,
    ) -> int:
        left, top, right, bottom = bounds
        width = right - left
        height = bottom - top
        strategy = normalize_strategy(direction)
        max_horizontal = max(4, (width - 12) // 2)
        if origin == "顶部中心":
            max_vertical = max(4, (height - top_offset - 6) // 2)
        else:
            max_vertical = max(4, (height - 12) // 2)
        if strategy == "水平往返":
            maximum = max_horizontal
        elif strategy == "垂直往返":
            maximum = max_vertical
        else:
            maximum = min(max_horizontal, max_vertical)
        return min(requested_distance, maximum)

    @staticmethod
    def build_drag_points(
        start_x: int,
        start_y: int,
        distance: int,
        cycles: int,
        direction: str,
        duration: int,
    ) -> list[tuple[int, int]]:
        strategy = normalize_strategy(direction)
        cycles = normalize_cycles(cycles)

        if strategy in ("顺时针圆形", "逆时针圆形"):
            distance_samples = math.ceil(2.0 * math.pi * distance / 28.0)
            samples_per_loop = max(32, min(96, max(round(duration / 8), distance_samples)))
            samples_per_loop += (-samples_per_loop) % 4
            quarter_samples = samples_per_loop // 4
            first_quarter = [
                (
                    round(distance * math.sin(index / quarter_samples * math.pi / 2.0)),
                    -round(distance * math.cos(index / quarter_samples * math.pi / 2.0)),
                )
                for index in range(quarter_samples + 1)
            ]
            loop_offsets = [first_quarter[0]]
            for quarter in range(4):
                for offset_x, offset_y in first_quarter[1:]:
                    for _ in range(quarter):
                        offset_x, offset_y = -offset_y, offset_x
                    loop_offsets.append((offset_x, offset_y))
            if strategy == "逆时针圆形":
                loop_offsets = [(-offset_x, offset_y) for offset_x, offset_y in loop_offsets]

            base_points = [(start_x + offset_x, start_y + offset_y) for offset_x, offset_y in loop_offsets]
            points = [base_points[0]]
            for _ in range(cycles):
                points.extend(base_points[1:])
            if strategy == "顺时针圆形":
                # A paired leftward pulse makes WeChat enter drag mode before
                # the clockwise arc starts, without adding any residual offset.
                origin = points[0]
                prime_distance = max(12, round(distance * 0.6))
                prime = (origin[0] - prime_distance, origin[1])
                prime_points = [origin]
                for segment_start, segment_end in ((origin, prime), (prime, origin)):
                    for step in range(1, 7):
                        progress = step / 6.0
                        point = (
                            round(segment_start[0] + (segment_end[0] - segment_start[0]) * progress),
                            round(segment_start[1] + (segment_end[1] - segment_start[1]) * progress),
                        )
                        if point != prime_points[-1]:
                            prime_points.append(point)
                points = [*prime_points, *points[1:]]
            return points

        if strategy == "八字轨迹":
            distance_samples = math.ceil(distance * 6.0 / 28.0)
            samples_per_loop = max(32, min(96, max(round(duration / 8), distance_samples)))
            samples_per_loop += (-samples_per_loop) % 4
            base_points: list[tuple[int, int]] = []
            for index in range(samples_per_loop + 1):
                if index == samples_per_loop:
                    phase = 2.0 * math.pi
                else:
                    quarter_progress = index / samples_per_loop * 4
                    quarter = int(quarter_progress)
                    local_progress = quarter_progress - quarter
                    phase = (quarter + local_progress) * math.pi / 2.0
                point = (
                    round(start_x + distance * math.sin(2.0 * phase)),
                    round(start_y - distance * math.cos(phase)),
                )
                if not base_points or point != base_points[-1]:
                    base_points.append(point)
            if base_points[-1] != base_points[0]:
                base_points.append(base_points[0])

            points = [base_points[0]]
            for _ in range(cycles // 2):
                points.extend(base_points[1:])
                points.extend(reversed(base_points[:-1]))
            return points

        if strategy == "垂直往返":
            # Press at the top endpoint, then sweep down and return to it.
            top_point = (start_x, start_y - distance)
            bottom_point = (start_x, start_y + distance)
            anchors = [top_point]
            for _ in range(cycles // 2):
                anchors.extend([bottom_point, top_point])
        else:
            center_point = (start_x, start_y)
            left_point = (start_x - distance, start_y)
            right_point = (start_x + distance, start_y)
            anchors = [center_point]
            for _ in range(cycles // 2):
                anchors.extend([left_point, center_point, right_point, center_point])

        segment_count = len(anchors) - 1
        steps_per_segment = max(5, min(59, round(duration / max(1, segment_count * 6))))
        if steps_per_segment % 2 == 0:
            steps_per_segment -= 1
        points = [anchors[0]]
        for segment_index in range(segment_count):
            start = anchors[segment_index]
            end = anchors[segment_index + 1]
            for step in range(1, steps_per_segment + 1):
                progress = step / steps_per_segment
                point = (
                    round(start[0] + (end[0] - start[0]) * progress),
                    round(start[1] + (end[1] - start[1]) * progress),
                )
                if point != points[-1]:
                    points.append(point)
        if strategy == "垂直往返":
            # A small paired side pulse prevents mini-programs from treating
            # consecutive identical vertical gestures as a duplicate.
            origin = points[0]
            prime_distance = min(24, max(12, round(distance * 0.1)))
            prime = (origin[0] + prime_distance, origin[1])
            prime_points = [origin]
            for segment_start, segment_end in ((origin, prime), (prime, origin)):
                for step in range(1, 5):
                    progress = step / 4.0
                    point = (
                        round(segment_start[0] + (segment_end[0] - segment_start[0]) * progress),
                        round(segment_start[1] + (segment_end[1] - segment_start[1]) * progress),
                    )
                    if point != prime_points[-1]:
                        prime_points.append(point)
            points = [*prime_points, *points[1:]]
        return points

    def vary_vertical_start(
        self,
        start_x: int,
        bounds: tuple[int, int, int, int],
        distance: int,
    ) -> int:
        left, _top, right, _bottom = bounds
        lane_distance = min(36, max(18, round(distance * 0.12)))
        lane_offsets = (0, lane_distance, -lane_distance)
        offset = lane_offsets[self.vertical_lane_index % len(lane_offsets)]
        self.vertical_lane_index += 1
        pulse_margin = min(24, max(12, round(distance * 0.1))) + 6
        return min(max(start_x + offset, left + pulse_margin), right - pulse_margin)

    def shake_target(self) -> None:
        if self.dragging:
            return
        if not self.target_hwnd or not user32.IsWindow(self.target_hwnd):
            self.status_var.set("请先选择窗口并点击“设为目标”")
            return
        if not user32.IsWindowVisible(self.target_hwnd):
            self.status_var.set("目标窗口当前不可见")
            return
        if user32.IsIconic(self.target_hwnd):
            self.status_var.set("目标窗口已最小化，无法拖动")
            return
        if not user32.IsWindowEnabled(self.target_hwnd):
            self.status_var.set("目标窗口当前不可用")
            return
        if window_has_higher_privilege(self.target_hwnd):
            self.status_var.set("权限不一致：请以管理员身份运行本工具，或以普通权限重启微信")
            return

        bounds = self.get_client_bounds(self.target_hwnd)
        if bounds is None:
            self.status_var.set("目标窗口客户区太小，无法设置拖动起点")
            return

        settings = self.get_settings()
        requested_distance = int(settings["distance"])
        duration = int(settings["duration"])
        cycles = int(settings["cycles"])
        direction = str(settings["direction"])
        top_offset = int(settings["top_offset"])
        if settings["origin"] == "顶部中心":
            client_height = bounds[3] - bounds[1]
            top_offset = min(top_offset, max(0, client_height - 14))
        distance = self.fit_distance_to_bounds(
            bounds,
            requested_distance,
            direction,
            str(settings["origin"]),
            top_offset,
        )
        start_x, start_y = self.get_drag_start(bounds, distance, direction, top_offset)
        if normalize_strategy(direction) == "垂直往返" and settings["origin"] != "当前鼠标":
            start_x = self.vary_vertical_start(start_x, bounds, distance)
        self.drag_points = self.build_drag_points(
            start_x,
            start_y,
            distance,
            cycles,
            direction,
            duration,
        )
        self.drag_index = 0
        self.drag_duration = duration
        self.drag_original_cursor = None
        self.drag_pressed = False
        self.dragging = True
        self.shake_button.configure(state="disabled", text="拖动中...")
        self.stop_button.configure(state="normal")
        fit_note = f"，窗口适配 {distance}px" if distance < requested_distance else ""
        self.status_var.set(
            f"正在拖动：{self.target_title}（{direction}，起点：{settings['origin']}{fit_note}）"
        )

        # Activating the target ensures the synthetic drag lands in the mini-program.
        if not user32.SetForegroundWindow(self.target_hwnd):
            self.finish_drag("无法激活目标窗口，请先把目标窗口置于前台")
            return
        self.root.after(90, self.begin_drag)

    def begin_drag(self) -> None:
        if not self.dragging:
            return
        if not self.target_hwnd or not user32.IsWindow(self.target_hwnd):
            self.finish_drag("目标窗口已关闭")
            return

        original = POINT()
        if not user32.GetCursorPos(ctypes.byref(original)):
            self.finish_drag("读取鼠标位置失败")
            return
        self.drag_original_cursor = (int(original.x), int(original.y))

        start_x, start_y = self.drag_points[0]
        if not user32.SetCursorPos(start_x, start_y):
            self.finish_drag("移动鼠标到拖动起点失败")
            return
        requested_method = self.input_method_var.get()
        if requested_method in ("标准", "兼容"):
            self.active_input_mode = requested_method
        elif self.active_input_mode is None:
            self.active_input_mode = self.detect_input_mode(start_x, start_y)
            if self.active_input_mode is None:
                self.finish_drag("模拟输入被系统拦截，请尝试以管理员身份运行")
                return
        user32.SetCursorPos(start_x, start_y)
        self.root.after(25, self.press_drag)

    def press_drag(self) -> None:
        if not self.dragging:
            return
        if not self.target_hwnd or not user32.IsWindow(self.target_hwnd):
            self.finish_drag("目标窗口已关闭")
            return
        if not self.send_drag_button(MOUSEEVENTF_LEFTDOWN):
            self.active_input_mode = None
            self.finish_drag("发送鼠标按下事件失败")
            return
        self.drag_pressed = True
        self.drag_index = 1
        self.drag_started_at = time.perf_counter()
        self.drag_watchdog_id = self.root.after(self.drag_duration + 1200, self.drag_timed_out)
        self.schedule_drag_next()

    @staticmethod
    def cursor_position() -> tuple[int, int] | None:
        point = POINT()
        if not user32.GetCursorPos(ctypes.byref(point)):
            return None
        return int(point.x), int(point.y)

    def detect_input_mode(self, start_x: int, start_y: int) -> str | None:
        left, top, width, height = virtual_screen_bounds()
        if start_x < left or start_x >= left + width or start_y < top or start_y >= top + height:
            return None
        if start_x + 8 < left + width:
            test_point = (start_x + 8, start_y)
        else:
            test_point = (start_x - 8, start_y)

        for mode, sender in (
            ("标准", send_mouse_move_absolute),
            ("兼容", send_mouse_move_legacy_absolute),
        ):
            user32.SetCursorPos(start_x, start_y)
            if not sender(*test_point):
                continue
            observed = self.cursor_position()
            user32.SetCursorPos(start_x, start_y)
            if observed is not None and max(
                abs(observed[0] - test_point[0]),
                abs(observed[1] - test_point[1]),
            ) <= 2:
                return mode
        return None

    def send_drag_button(self, flags: int) -> bool:
        if self.active_input_mode == "兼容":
            return send_mouse_button_legacy(flags)
        return send_mouse_button(flags)

    def send_drag_move(self, x: int, y: int) -> bool:
        if self.active_input_mode == "兼容":
            return send_mouse_move_legacy_absolute(x, y)
        return send_mouse_move_absolute(x, y)

    def schedule_drag_next(self) -> None:
        step_count = max(1, len(self.drag_points) - 1)
        target_ms = self.drag_duration * self.drag_index / step_count
        elapsed_ms = (time.perf_counter() - self.drag_started_at) * 1000.0
        self.root.after(max(1, round(target_ms - elapsed_ms)), self.drag_next)

    def drag_next(self) -> None:
        if not self.dragging:
            return
        if self.drag_index >= len(self.drag_points):
            self.release_drag()
            return

        point_x, point_y = self.drag_points[self.drag_index]
        if not self.send_drag_move(point_x, point_y):
            self.active_input_mode = None
            self.finish_drag("拖动鼠标失败")
            return
        self.drag_index += 1
        if self.drag_index < len(self.drag_points):
            self.schedule_drag_next()
        else:
            # Give the target time to process the final move before releasing.
            self.root.after(20, self.release_drag)

    def release_drag(self) -> None:
        if not self.dragging:
            return
        self.finish_drag(f"拖动完成（{self.active_input_mode or '标准'}输入）")

    def drag_timed_out(self) -> None:
        self.drag_watchdog_id = None
        if self.dragging:
            self.finish_drag("拖动超时，已自动释放鼠标")

    def stop_drag(self) -> None:
        if not self.dragging:
            self.status_var.set("当前没有正在执行的拖动")
            return
        self.finish_drag("已手动停止")

    def finish_drag(self, message: str) -> None:
        if self.drag_watchdog_id is not None:
            try:
                self.root.after_cancel(self.drag_watchdog_id)
            except tk.TclError:
                pass
            self.drag_watchdog_id = None
        if self.drag_pressed:
            if not self.send_drag_button(MOUSEEVENTF_LEFTUP):
                message = "发送鼠标释放事件失败"
            self.drag_pressed = False
        if self.drag_original_cursor is not None and self.restore_cursor_var.get():
            user32.SetCursorPos(*self.drag_original_cursor)
        self.drag_original_cursor = None
        self.drag_points = []
        self.dragging = False
        self.shake_button.configure(state="normal", text="晃一下")
        self.stop_button.configure(state="disabled")
        self.status_var.set(message)

    def start_hotkeys(self) -> None:
        self.hotkey_thread = threading.Thread(target=self.hotkey_loop, name="screen-shaker-hotkeys", daemon=True)
        self.hotkey_thread.start()

    def call_on_ui(self, callback, *args) -> None:
        try:
            self.root.after(0, callback, *args)
        except tk.TclError:
            pass

    def hotkey_loop(self) -> None:
        # Touch the queue before PostThreadMessageW is used during shutdown.
        self.hotkey_thread_id = int(kernel32.GetCurrentThreadId())
        queue_message = MSG()
        user32.PeekMessageW(ctypes.byref(queue_message), 0, 0, 0, 0)
        if self.stop_hotkeys.is_set():
            return

        modifiers = MOD_CONTROL | MOD_ALT
        registered_lock = bool(user32.RegisterHotKey(0, HOTKEY_LOCK, modifiers, VK_F7))
        registered_shake = bool(user32.RegisterHotKey(0, HOTKEY_SHAKE, modifiers, VK_F8))
        registered_stop = bool(user32.RegisterHotKey(0, HOTKEY_STOP, modifiers, VK_F9))
        if not registered_lock or not registered_shake or not registered_stop:
            if registered_lock:
                user32.UnregisterHotKey(0, HOTKEY_LOCK)
            if registered_shake:
                user32.UnregisterHotKey(0, HOTKEY_SHAKE)
            if registered_stop:
                user32.UnregisterHotKey(0, HOTKEY_STOP)
            self.call_on_ui(self.status_var.set, "全局快捷键注册失败，按钮仍然可用")
            return

        self.call_on_ui(self.status_var.set, "快捷键已启用")
        message = MSG()
        try:
            while not self.stop_hotkeys.is_set():
                result = user32.GetMessageW(ctypes.byref(message), 0, 0, 0)
                if result <= 0:
                    break
                if message.message == WM_HOTKEY:
                    if int(message.wParam) == HOTKEY_LOCK:
                        self.call_on_ui(self.lock_foreground_window)
                    elif int(message.wParam) == HOTKEY_SHAKE:
                        self.call_on_ui(self.shake_from_hotkey)
                    elif int(message.wParam) == HOTKEY_STOP:
                        self.call_on_ui(self.stop_drag)
        finally:
            user32.UnregisterHotKey(0, HOTKEY_LOCK)
            user32.UnregisterHotKey(0, HOTKEY_SHAKE)
            user32.UnregisterHotKey(0, HOTKEY_STOP)

    def close(self) -> None:
        if self.dragging:
            self.finish_drag("已停止")
        self.save_settings()
        self.stop_hotkeys.set()
        if self.hotkey_thread_id:
            user32.PostThreadMessageW(self.hotkey_thread_id, WM_QUIT, 0, 0)
        self.root.destroy()


def main() -> None:
    set_process_dpi_aware()
    root = tk.Tk()
    ShakeApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
