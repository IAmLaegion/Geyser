import ctypes
import sys
import time
import winreg
from ctypes import wintypes
from pathlib import Path

user32 = ctypes.WinDLL("user32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi")

LONG_PTR = ctypes.c_ssize_t
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.EnumChildWindows.argtypes = [wintypes.HWND, WNDENUMPROC, wintypes.LPARAM]
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindow.argtypes = [wintypes.HWND]
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongPtrW.restype = LONG_PTR
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, LONG_PTR]
user32.SetWindowLongPtrW.restype = LONG_PTR
user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
dwmapi.DwmSetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]

GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WM_HOTKEY = 0x0312


# ---- window enumeration ---------------------------------------------------

def top_level_windows():
    found = []

    def cb(hwnd, _):
        found.append(hwnd)
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return found


def child_windows(hwnd):
    found = []

    def cb(child, _):
        found.append(child)
        return True

    user32.EnumChildWindows(hwnd, WNDENUMPROC(cb), 0)
    return found


def window_text(hwnd) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def window_pid(hwnd) -> int:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def is_visible(hwnd) -> bool:
    return bool(user32.IsWindowVisible(hwnd))


# ---- focus guard ----------------------------------------------------------

class NoActivate:
    """Marks a window WS_EX_NOACTIVATE while a click is delivered, so the click can't pull it to the front.

    The style is held briefly after the click because the target app may react to it asynchronously,
    then only our bit is cleared, so the user can click into the window normally again.
    """

    def __init__(self, hwnd, hold=0.5):
        self.hwnd = hwnd
        self.hold = hold
        self.applied = False

    def __enter__(self):
        style = user32.GetWindowLongPtrW(self.hwnd, GWL_EXSTYLE)
        if style and not style & WS_EX_NOACTIVATE:
            user32.SetWindowLongPtrW(self.hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE)
            self.applied = True
        return self

    def __exit__(self, *exc):
        if not self.applied:
            return False
        time.sleep(self.hold)
        if user32.IsWindow(self.hwnd):
            style = user32.GetWindowLongPtrW(self.hwnd, GWL_EXSTYLE)
            user32.SetWindowLongPtrW(self.hwnd, GWL_EXSTYLE, style & ~WS_EX_NOACTIVATE)
        return False


# ---- title bar ------------------------------------------------------------

def style_title_bar(hwnd, caption_hex=None):
    """Dark title bar on Windows 10 20H1+, plus a matching caption colour on Windows 11."""
    try:
        dark = ctypes.c_int(1)
        dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark), ctypes.sizeof(dark))
        if caption_hex:
            r, g, b = (int(caption_hex[i:i + 2], 16) for i in (1, 3, 5))
            color = ctypes.c_int(r | (g << 8) | (b << 16))
            dwmapi.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(color), ctypes.sizeof(color))
    except OSError:
        pass


# ---- global hotkey --------------------------------------------------------

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
_MODS = {"CTRL": MOD_CONTROL, "CONTROL": MOD_CONTROL, "ALT": MOD_ALT, "SHIFT": MOD_SHIFT, "META": MOD_WIN, "WIN": MOD_WIN}
_KEYS = {
    "SPACE": 0x20, "PGUP": 0x21, "PGDOWN": 0x22, "END": 0x23, "HOME": 0x24,
    "LEFT": 0x25, "UP": 0x26, "RIGHT": 0x27, "DOWN": 0x28, "INS": 0x2D, "INSERT": 0x2D,
    "DEL": 0x2E, "DELETE": 0x2E, "PAUSE": 0x13, "SCROLLLOCK": 0x91,
}


def parse_hotkey(text):
    """'Ctrl+Alt+G' -> (modifiers, vk). Returns None unless there's at least one modifier and one key."""
    if not text:
        return None
    mods, vk = 0, None
    for part in (p.strip().upper() for p in text.split("+") if p.strip()):
        if part in _MODS:
            mods |= _MODS[part]
        elif len(part) == 1 and part.isalnum():
            vk = ord(part)
        elif part.startswith("F") and part[1:].isdigit() and 1 <= int(part[1:]) <= 24:
            vk = 0x6F + int(part[1:])
        elif part in _KEYS:
            vk = _KEYS[part]
        else:
            return None
    if not mods or vk is None:
        return None
    return mods, vk


def register_hotkey(hwnd, hotkey_id, mods, vk) -> bool:
    return bool(user32.RegisterHotKey(hwnd, hotkey_id, mods | MOD_NOREPEAT, vk))


def unregister_hotkey(hwnd, hotkey_id):
    user32.UnregisterHotKey(hwnd, hotkey_id)


# ---- start with Windows ---------------------------------------------------

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_RUN_VALUE = "Geyser"


def startup_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --minimized'
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    exe = pythonw if pythonw.exists() else Path(sys.executable)
    run = Path(__file__).resolve().parent.parent / "run.py"
    return f'"{exe}" "{run}" --minimized'


def startup_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.QueryValueEx(key, _RUN_VALUE)
            return True
    except OSError:
        return False


def set_startup(enabled: bool):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, _RUN_VALUE, 0, winreg.REG_SZ, startup_command())
        else:
            try:
                winreg.DeleteValue(key, _RUN_VALUE)
            except FileNotFoundError:
                pass


def set_app_user_model_id(app_id):
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except (OSError, AttributeError):
        pass
