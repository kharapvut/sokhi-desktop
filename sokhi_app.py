# -*- coding: utf-8 -*-
"""
Sokhi App Launcher — Desktop Sokhi-র আসল app-রূপ (Windows .exe)
================================================================
এই launcher-টাই PyInstaller দিয়ে Sokhi.exe হয়। কাজ খুব সরল:

  ১. পাশে থাকা বর্তমান sokhi.py-কেই নিজের process-এর একটা thread-এ
     চালায় (runpy দিয়ে) — sokhi.py exe-র ভেতরে বন্দি নয়, আলাদা
     ফাইল হিসেবেই থাকে, তাই GitHub থেকে "আপগ্রেড চেক করো" দিলে নতুন
     sokhi.py নেমে আসে আর পরের চালুতে সেটাই চলে। Self-update অক্ষত।
  ২. Port 8765-তে সার্ভার ওঠা পর্যন্ত অপেক্ষা করে।
  ৩. তারপর Sokhi-র নিজের উইন্ডো খোলে (pywebview) — browser-এর ট্যাব/
     অ্যাড্রেস বার নেই। pywebview না থাকলে Edge/Chrome --app মোড,
     তাও না থাকলে সাধারণ browser।
  ৪. সার্ভার আগেই চলমান থাকলে (port busy) দ্বিতীয় কপি চালায় না —
     শুধু উইন্ডো খোলে।
  ৫. উইন্ডো বন্ধ হলে সার্ভারসহ সুন্দরভাবে বন্ধ হয়ে যায়।
     কোনো কালো console উইন্ডো নয় (exe --windowed মোডে বানানো)।

যোগ হওয়া launcher-ফিচার (সবই optional/lazy — pystray/PIL না থাকলে
app আগের মতোই চলে, শুধু log-এ নোট থাকে; প্রতিটি অংশ আলাদা
try/except-এ মোড়া, একটা ভাঙলে পুরোটা ভাঙে না):
  * System tray (pystray) + toast notification + toast_queue watcher
  * Main window close/minimize = tray-তে hide; quit শুধু tray মেনু থেকে
  * ভাসমান ছোট্ট mini window, js_api (show_main/fullscreen)
  * Global hotkey Ctrl+Alt+S (শুধু Windows), PC health নজরদারি,
    চোখের বিরতি (20-20-20), clipboard নজরদারি (শুধু Windows)
  * Auto-update যাচাই (শুধু toast — নিজে কিছু download/install করে না)
  * --explain <file>: ফাইল Sokhi-কে দিয়ে সহজ বাংলায় বোঝানো

Python-মতো ডাক (mux): sokhi.py ভেতর থেকে মাঝে মাঝে
  [sys.executable, "-m", "edge_tts", ...], ["-m", "py_compile", ...],
  ["-c", "..."] চালায়। Frozen exe-তে sys.executable মানে Sokhi.exe
নিজেই — তাই launcher শুরুতে argv দেখে: "-m <module>" বা "-c <code>"
থাকলে সে app না খুলে ঠিক Python-এর মতো সেই কাজটা করে বেরিয়ে যায়।
"""
import base64
import ctypes
import hashlib
import json
import os
import runpy
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

try:
    # Frozen bundle-এ edge_tts (ও তার সঙ্গীরা) যেন অবশ্যই ঢোকে —
    # শুধু এই import-টার জন্যই রাখা; ব্যর্থ হলে সমস্যা নেই, sokhi.py
    # নিজেই PATH-এর edge-tts.exe খুঁজে নেয়।
    import edge_tts  # noqa: F401
except Exception:
    edge_tts = None

PORT = 8765
URL = f"http://localhost:{PORT}"
APP_NAME = "Sokhi"


def app_dir() -> Path:
    """exe (frozen) হলে exe-র পাশের ফোল্ডার; নইলে এই ফাইলের ফোল্ডার।"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


APP_DIR = app_dir()
SOKHI_PY = APP_DIR / "sokhi.py"
DATA_DIR = APP_DIR / "data"
LOG_FILE = DATA_DIR / "sokhi-app.log"
ICON_FILE = APP_DIR / "sokhi.ico"
PNG_FILE = APP_DIR / "sokhi.png"

# launcher-এর নিজের ফাইলগুলো (সবই data/-র ভেতরে)
SETTINGS_FILE = DATA_DIR / "app-settings.json"
STATE_FILE = DATA_DIR / "app-state.json"
TOAST_QUEUE_DIR = DATA_DIR / "toast_queue"
CLIPBOARD_FILE = DATA_DIR / "clipboard_last.txt"
PIN_FILE = DATA_DIR / "pin.txt"
CONFIG_FILE = DATA_DIR / "config.json"
VERSION_FILE = DATA_DIR / "version.json"

_IS_WINDOWS = os.name == "nt" or sys.platform.startswith("win")


def _log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    try:
        print(line, flush=True)
    except Exception:
        pass
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


# ------------------------------------------------------- shared state
_quit_event = threading.Event()   # fallback keep-alive loop এই flag দেখে
_tray_icon = None                 # pystray Icon (থাকলে)
_main_window = None               # pywebview main window (থাকলে)
_mini_window = None               # pywebview mini window (থাকলে)
_webview_mod = None               # import করা webview module (থাকলে)
_first_hide_toasted = False       # "tray-তে চলছে" toast একবারই
_is_fullscreen = False            # js_api exit_fullscreen-এর হিসাব
_settings = None                  # app-settings.json cache
_settings_lock = threading.Lock()
_state_lock = threading.Lock()
_last_clipboard_hash = ""
_last_clipboard_toast_at = 0.0


# ------------------------------------------------------------------ stdio
def _stdio_to_log() -> None:
    """--windowed exe-তে sys.stdout/stderr থাকে না (None) — sokhi.py-র
    print() তাহলে crash করত। None থাকলে log ফাইলে পাঠিয়ে দিই।"""
    if sys.stdout is not None and sys.stderr is not None:
        return
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        fh = open(LOG_FILE, "a", encoding="utf-8", buffering=1)
    except Exception:
        fh = open(os.devnull, "w")
    if sys.stdout is None:
        sys.stdout = fh
    if sys.stderr is None:
        sys.stderr = fh


def _stdio_to_pipes() -> None:
    """Mux (subprocess) মোডে: বাবা-process (sokhi.py) capture_output দিয়ে
    ডাকে — আসল pipe-গুলোই (fd 1/2) জোড়া দেওয়ার চেষ্টা; না পারলে devnull।"""
    for fd, name in ((1, "stdout"), (2, "stderr")):
        if getattr(sys, name) is None:
            stream = None
            try:
                stream = os.fdopen(fd, "w", closefd=False)
            except Exception:
                stream = None
            if stream is None:
                stream = open(os.devnull, "w")
            setattr(sys, name, stream)


# -------------------------------------------------------------------- mux
def _mux_if_needed() -> bool:
    """argv-তে "-m <module>" বা "-c <code>" থাকলে Python-এর মতো আচরণ।
    True ফেরত দিলে caller-এর আর কিছু করার নেই (process exit হবে)।"""
    args = sys.argv[1:]
    if not args:
        return False
    if args[0] == "-m" and len(args) >= 2:
        _stdio_to_pipes()
        module = args[1]
        if module == "pip":
            print("এই app-এর ভেতরে pip নেই — edge-tts আগে থেকেই বসানো আছে।",
                  file=sys.stderr)
            sys.exit(3)
        sys.argv = [module] + args[2:]
        try:
            runpy.run_module(module, run_name="__main__", alter_sys=True)
        except SystemExit as e:
            sys.exit(e.code if isinstance(e.code, int) else 0)
        except ImportError as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)
        sys.exit(0)
    if args[0] == "-c" and len(args) >= 2:
        _stdio_to_pipes()
        code = args[1]
        sys.argv = ["-c"] + args[2:]
        try:
            exec(compile(code, "<string>", "exec"),
                 {"__name__": "__main__", "__file__": "<string>",
                  "__builtins__": __builtins__})
        except SystemExit as e:
            sys.exit(e.code if isinstance(e.code, int) else 0)
        sys.exit(0)
    return False


# ------------------------------------------------------- settings / state
_DEFAULT_SETTINGS = {"clipboard_on": True, "eye_break_on": True,
                     "mini_on": True}


def _load_settings() -> dict:
    """data/app-settings.json পড়ে (না থাকলে/ভাঙা হলে default)।"""
    global _settings
    with _settings_lock:
        if _settings is not None:
            return _settings
        data = dict(_DEFAULT_SETTINGS)
        try:
            if SETTINGS_FILE.exists():
                raw = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    for key in data:
                        if key in raw:
                            data[key] = bool(raw[key])
        except Exception as e:
            _log(f"app-settings.json পড়া গেল না, default নিলাম: {e!r}")
        _settings = data
        return _settings


def _save_settings() -> None:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with _settings_lock:
            SETTINGS_FILE.write_text(
                json.dumps(_settings or _DEFAULT_SETTINGS,
                           ensure_ascii=False, indent=2),
                encoding="utf-8")
    except Exception as e:
        _log(f"app-settings.json লেখা গেল না: {e!r}")


def _setting(key: str) -> bool:
    try:
        return bool(_load_settings().get(key, _DEFAULT_SETTINGS.get(key)))
    except Exception:
        return bool(_DEFAULT_SETTINGS.get(key, False))


def _set_setting(key: str, value: bool) -> None:
    try:
        _load_settings()[key] = bool(value)
        _save_settings()
    except Exception as e:
        _log(f"সেটিং বদলানো গেল না ({key}): {e!r}")


def _load_state() -> dict:
    try:
        if STATE_FILE.exists():
            raw = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return raw
    except Exception as e:
        _log(f"app-state.json পড়া গেল না: {e!r}")
    return {}


def _save_state(state: dict) -> None:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False,
                                         indent=2), encoding="utf-8")
    except Exception as e:
        _log(f"app-state.json লেখা গেল না: {e!r}")


def _warned_today(key: str) -> bool:
    """আজ এই সতর্কতাটা ইতিমধ্যে দেওয়া হয়েছে কি না (দিনে একবার)।"""
    with _state_lock:
        state = _load_state()
        today = time.strftime("%Y-%m-%d")
        return (state.get("date") == today
                and key in (state.get("daily_keys") or []))


def _mark_warned_today(key: str) -> None:
    with _state_lock:
        state = _load_state()
        today = time.strftime("%Y-%m-%d")
        if state.get("date") != today:
            state["date"] = today
            state["daily_keys"] = []
        keys = state.setdefault("daily_keys", [])
        if key not in keys:
            keys.append(key)
        _save_state(state)


def _warn_once_per_day(key: str, title: str, message: str) -> None:
    try:
        if _warned_today(key):
            return
        _mark_warned_today(key)
        show_toast(title, message)
    except Exception as e:
        _log(f"দৈনিক সতর্কতা ব্যর্থ ({key}): {e!r}")


def _once_ever(key: str) -> bool:
    """এই key আগে চিহ্নিত হলে True; না হলে এখনই চিহ্নিত করে False।"""
    with _state_lock:
        state = _load_state()
        keys = state.setdefault("once_keys", [])
        if key in keys:
            return True
        keys.append(key)
        _save_state(state)
        return False


# ------------------------------------------------------------------- toast
def show_toast(title: str, msg: str) -> None:
    """Tray icon থাকলে pystray notify(), নইলে শুধু log। কখনো crash নয়।"""
    try:
        icon = _tray_icon
        if icon is not None:
            try:
                icon.notify(msg, title)
                return
            except Exception as e:
                _log(f"tray notify ব্যর্থ, log-এ রাখছি: {e!r}")
        _log(f"TOAST [{title}] {msg}")
    except Exception as e:
        try:
            _log(f"TOAST ব্যর্থ [{title}] {msg}: {e!r}")
        except Exception:
            pass


def _toast_watcher_loop() -> None:
    """data/toast_queue/*.json প্রতি ২ সেকেন্ডে পড়ে toast করে মোছে।
    sokhi.py (বা অন্য অংশ) ফাইল ফেললেই launcher toast দেখায়। নষ্ট
    ফাইলও মোছে — সারি যেন আটকে না থাকে।"""
    while not _quit_event.is_set():
        try:
            TOAST_QUEUE_DIR.mkdir(parents=True, exist_ok=True)
            for path in sorted(TOAST_QUEUE_DIR.glob("*.json")):
                try:
                    raw = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(raw, dict):
                        title = str(raw.get("title") or "Sokhi")
                        message = str(raw.get("message")
                                      or raw.get("msg") or "")
                        if message:
                            show_toast(title, message)
                except Exception as e:
                    _log(f"toast_queue-র নষ্ট ফাইল মুছছি "
                         f"({path.name}): {e!r}")
                finally:
                    try:
                        path.unlink()
                    except Exception:
                        pass
        except Exception as e:
            _log(f"toast watcher-এ ভুল: {e!r}")
        _quit_event.wait(2.0)


# -------------------------------------------------------------------- tray
def _target_exe() -> Path:
    """Auto-start shortcut-এর TargetPath: frozen হলে আসল exe, নইলে
    পাশের Sokhi.exe (না থাকলেও নামটাই — shortcut তখন exe এলে কাজ করবে)।"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable)
    return APP_DIR / "Sokhi.exe"


def _startup_lnk_path():
    try:
        appdata = os.environ.get("APPDATA", "")
        if not appdata:
            return None
        return (Path(appdata) / "Microsoft" / "Windows" / "Start Menu"
                / "Programs" / "Startup" / "Sokhi.lnk")
    except Exception:
        return None


def _autostart_on() -> bool:
    try:
        lnk = _startup_lnk_path()
        return bool(lnk and lnk.exists())
    except Exception:
        return False


def _set_autostart(on: bool) -> None:
    """Startup shortcut বানানো/মোছা — PowerShell (WScript.Shell) দিয়ে।"""
    try:
        lnk = _startup_lnk_path()
        if lnk is None:
            _log("auto-start: APPDATA পাওয়া গেল না।")
            return
        if not on:
            try:
                if lnk.exists():
                    lnk.unlink()
                    _log("auto-start বন্ধ: Startup shortcut মোছা হলো।")
            except Exception as e:
                _log(f"auto-start shortcut মোছা গেল না: {e!r}")
            return
        lnk.parent.mkdir(parents=True, exist_ok=True)

        def _psq(p) -> str:  # PowerShell single-quote escaping
            return str(p).replace("'", "''")

        target = _target_exe()
        icon_loc = ICON_FILE if ICON_FILE.exists() else target
        script = (
            "$ws = New-Object -ComObject WScript.Shell; "
            f"$sc = $ws.CreateShortcut('{_psq(lnk)}'); "
            f"$sc.TargetPath = '{_psq(target)}'; "
            f"$sc.WorkingDirectory = '{_psq(APP_DIR)}'; "
            f"$sc.IconLocation = '{_psq(icon_loc)}'; "
            "$sc.Save()"
        )
        kwargs = {}
        if _IS_WINDOWS:
            kwargs["creationflags"] = getattr(
                subprocess, "CREATE_NO_WINDOW", 0)
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive",
             "-Command", script],
            capture_output=True, text=True, timeout=30, **kwargs)
        if res.returncode == 0 and lnk.exists():
            _log("auto-start চালু: Startup shortcut বানানো হলো।")
        else:
            _log(f"auto-start shortcut বানানো গেল না "
                 f"(rc={res.returncode}): {(res.stderr or '')[:300]}")
    except Exception as e:
        _log(f"auto-start বদলাতে ভুল: {e!r}")


def _tray_image():
    """sokhi.png → sokhi.ico → PIL দিয়ে আঁকা সরল orb (এই ক্রমে)।"""
    from PIL import Image, ImageDraw
    for cand in (PNG_FILE, ICON_FILE):
        try:
            if cand.exists():
                img = Image.open(cand)
                img.load()
                return img.convert("RGBA")
        except Exception as e:
            _log(f"tray icon ছবি পড়া গেল না ({cand.name}): {e!r}")
    # সরল orb: গাঢ় নীল পটে আকাশি-বেগুনি গোলক + ছোট্ট highlight
    img = Image.new("RGBA", (64, 64), (13, 19, 48, 255))
    d = ImageDraw.Draw(img)
    d.ellipse([10, 10, 54, 54], fill=(56, 189, 248, 255))
    d.ellipse([26, 30, 54, 54], fill=(139, 92, 246, 255))
    d.ellipse([10, 10, 54, 34], fill=(165, 243, 252, 255))
    d.ellipse([18, 14, 30, 26], fill=(255, 255, 255, 220))
    return img


def _quit_app(icon=None, item=None) -> None:
    """সম্পূর্ণ বন্ধ — শুধু tray মেনু থেকেই ডাকা হয়।"""
    _log("tray মেনু থেকে সম্পূর্ণ বন্ধ করা হচ্ছে।")
    _quit_event.set()
    try:
        tray = icon if icon is not None else _tray_icon
        if tray is not None:
            tray.stop()
    except Exception:
        pass
    for win in (_main_window, _mini_window):
        try:
            if win is not None:
                win.destroy()
        except Exception:
            pass
    os._exit(0)


def _start_tray() -> None:
    """pystray tray icon — না থাকলে log-এ নোট দিয়ে চুপচাপ এগিয়ে যাই।"""
    global _tray_icon
    try:
        import pystray
        from PIL import Image  # noqa: F401  (থাকা নিশ্চিত করা)
    except Exception as e:
        _log(f"tray পাওয়া যাচ্ছে না (pystray/PIL নেই) — app tray ছাড়াই "
             f"চলবে: {e!r}")
        return
    try:
        def _refresh(icon):
            try:
                icon.update_menu()
            except Exception:
                pass

        def _on_open(icon, item):
            show_main()

        def _on_mini(icon, item):
            new_val = not _setting("mini_on")
            _set_mini_visible(new_val)
            _refresh(icon)

        def _on_autostart(icon, item):
            _set_autostart(not _autostart_on())
            _refresh(icon)

        def _on_clipboard(icon, item):
            _set_setting("clipboard_on", not _setting("clipboard_on"))
            _refresh(icon)

        def _on_eye(icon, item):
            _set_setting("eye_break_on", not _setting("eye_break_on"))
            _refresh(icon)

        menu = pystray.Menu(
            pystray.MenuItem("Sokhi খোলো", _on_open, default=True),
            pystray.MenuItem(
                "ভাসমান ছোট্ট Sokhi", _on_mini,
                checked=lambda item: _setting("mini_on")),
            pystray.MenuItem(
                "PC চালু হলে auto-start", _on_autostart,
                checked=lambda item: _autostart_on()),
            pystray.MenuItem(
                "ক্লিপবোর্ড-নজর", _on_clipboard,
                checked=lambda item: _setting("clipboard_on")),
            pystray.MenuItem(
                "চোখের বিরতি মনে করানো", _on_eye,
                checked=lambda item: _setting("eye_break_on")),
            pystray.MenuItem("সম্পূর্ণ বন্ধ করো", _quit_app),
        )
        icon = pystray.Icon("sokhi", _tray_image(), "Sokhi", menu)
        _tray_icon = icon
        if hasattr(icon, "run_detached"):
            icon.run_detached()
        else:
            threading.Thread(target=icon.run, name="sokhi-tray",
                             daemon=True).start()
        _log("tray icon চালু হলো।")
    except Exception as e:
        _tray_icon = None
        _log(f"tray চালু করা গেল না — app tray ছাড়াই চলবে: {e!r}")


# ------------------------------------------------------- window helpers
def show_main() -> None:
    """Main window সামনে আনা (tray মেনু / mini ক্লিক / hotkey থেকে)।"""
    try:
        win = _main_window
        if win is not None:
            try:
                win.show()
            except Exception:
                pass
            try:
                win.restore()
            except Exception:
                pass
            return
        # pywebview window নেই (fallback browser মোড) — browser-এ খুলি
        _log("show_main: কোনো app window নেই, browser-এ খুলছি।")
        try:
            _orig_browser_open(URL)
        except Exception as e:
            _log(f"show_main browser খোলা ব্যর্থ: {e!r}")
    except Exception as e:
        _log(f"show_main ব্যর্থ: {e!r}")


def _set_mini_visible(visible: bool) -> None:
    """Mini window দেখানো/লুকানো + সেটিং সংরক্ষণ।"""
    try:
        _set_setting("mini_on", bool(visible))
        win = _mini_window
        if win is not None:
            try:
                if visible:
                    win.show()
                else:
                    win.hide()
            except Exception as e:
                _log(f"mini window show/hide ব্যর্থ: {e!r}")
        elif visible:
            # window এখনো বানানো হয়নি (আগে mini_on=false ছিল) —
            # সম্ভব হলে এখন বানাই, নইলে পরের চালুতে আসবে।
            try:
                _create_mini_window()
            except Exception as e:
                _log(f"mini window এখন বানানো গেল না — পরের চালুতে "
                     f"আসবে: {e!r}")
    except Exception as e:
        _log(f"mini toggle ব্যর্থ: {e!r}")


def _on_main_closing(*args, **kwargs):
    """Close চাপলে বন্ধ নয় — tray-তে লুকিয়ে থাকে। False = veto।"""
    global _first_hide_toasted
    try:
        if _main_window is not None:
            _main_window.hide()
    except Exception as e:
        _log(f"main window hide ব্যর্থ: {e!r}")
    try:
        if not _first_hide_toasted:
            _first_hide_toasted = True
            show_toast("Sokhi",
                       "Sokhi tray-তে চলছে — tray আইকন থেকে আবার "
                       "খোলা যাবে, পুরোপুরি বন্ধ tray মেনু থেকে।")
    except Exception:
        pass
    return False


def _on_main_minimized(*args, **kwargs):
    try:
        if _main_window is not None:
            _main_window.hide()
    except Exception as e:
        _log(f"minimize-এ hide ব্যর্থ: {e!r}")
    return None


class Api:
    """pywebview js_api — একটাই অবজেক্ট, দুই window-তেই দেওয়া হয়।
    পেজ থেকে: window.pywebview.api.show_main() ইত্যাদি।"""

    def show_main(self):
        show_main()

    def toggle_fullscreen(self):
        global _is_fullscreen
        try:
            if _main_window is not None:
                _main_window.toggle_fullscreen()
                _is_fullscreen = not _is_fullscreen
        except Exception as e:
            _log(f"toggle_fullscreen ব্যর্থ: {e!r}")

    def exit_fullscreen(self):
        global _is_fullscreen
        try:
            if _main_window is not None and _is_fullscreen:
                _main_window.toggle_fullscreen()
                _is_fullscreen = False
        except Exception as e:
            _log(f"exit_fullscreen ব্যর্থ: {e!r}")


_api = Api()


MINI_HTML = """<!doctype html>
<html lang="bn"><head><meta charset="utf-8"><title>Sokhi</title>
<style>
  html,body{margin:0;height:100%;overflow:hidden;cursor:pointer;
       background:#0d1330;color:#e8ecff;user-select:none;
       font-family:'Hind Siliguri','Nirmala UI',sans-serif}
  body{display:flex;flex-direction:column;gap:8px;align-items:center;
       justify-content:center}
  .orb{width:74px;height:74px;border-radius:50%;
       background:radial-gradient(circle at 35% 30%,#a5f3fc,#38bdf8 45%,#8b5cf6 100%);
       box-shadow:0 0 34px #38bdf888;animation:p 1.8s ease-in-out infinite}
  @keyframes p{0%,100%{transform:scale(1)}50%{transform:scale(1.06)}}
  div.name{font-size:16px;font-weight:600}
  div.hint{font-size:11px;opacity:.65}
</style></head>
<body onclick="window.pywebview && window.pywebview.api && window.pywebview.api.show_main()">
  <div class="orb"></div><div class="name">Sokhi</div>
  <div class="hint">খুলতে ক্লিক করো</div>
</body></html>"""


def _mini_position():
    """ডান-নিচ কোণ (Windows-এ আসল screen মাপ), নইলে (100, 100)।"""
    try:
        if _IS_WINDOWS:
            user32 = ctypes.windll.user32  # type: ignore[attr-defined]
            w = int(user32.GetSystemMetrics(0))
            h = int(user32.GetSystemMetrics(1))
            if w > 200 and h > 220:
                return (w - 150 - 16, h - 170 - 48)
    except Exception as e:
        _log(f"mini position হিসাব ব্যর্থ: {e!r}")
    return (100, 100)


def _create_mini_window():
    """ভাসমান ছোট্ট Sokhi — frameless, সবসময় উপরে, ডান-নিচ কোণে।"""
    global _mini_window
    if _mini_window is not None or _webview_mod is None:
        return _mini_window
    x, y = _mini_position()
    _mini_window = _webview_mod.create_window(
        "Sokhi mini", html=MINI_HTML, js_api=_api,
        width=150, height=170, x=x, y=y,
        frameless=True, on_top=True, resizable=False)
    return _mini_window


# ------------------------------------------------------------- hotkey
def _hotkey_loop() -> None:
    """Ctrl+Alt+S — শুধু Windows (ctypes user32 RegisterHotKey)।"""
    try:
        if not _IS_WINDOWS:
            _log("hotkey শুধু Windows-এ — এই সিস্টেমে skip করা হলো।")
            return
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        MOD_ALT = 0x0001
        MOD_CONTROL = 0x0002
        MOD_NOREPEAT = 0x4000
        WM_HOTKEY = 0x0312
        VK_S = 0x53

        class _POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        class _MSG(ctypes.Structure):
            _fields_ = [("hwnd", ctypes.c_void_p),
                        ("message", ctypes.c_uint),
                        ("wParam", ctypes.c_size_t),
                        ("lParam", ctypes.c_ssize_t),
                        ("time", ctypes.c_ulong),
                        ("pt", _POINT)]

        try:
            user32.RegisterHotKey.restype = ctypes.c_bool
        except Exception:
            pass
        if not user32.RegisterHotKey(
                None, 1, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, VK_S):
            _log("Ctrl+Alt+S hotkey নিবন্ধন করা গেল না "
                 "(হয়তো অন্য app ধরে রেখেছে)।")
            return
        _log("hotkey চালু: Ctrl+Alt+S চাপলে Sokhi সামনে আসবে।")
        try:
            msg = _MSG()
            while not _quit_event.is_set():
                ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if ret <= 0:  # WM_QUIT বা ভুল
                    break
                if msg.message == WM_HOTKEY:
                    show_main()
                try:
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
                except Exception:
                    pass
        finally:
            try:
                user32.UnregisterHotKey(None, 1)
            except Exception:
                pass
    except Exception as e:
        _log(f"hotkey thread ব্যর্থ — বাকি app চলবে: {e!r}")


# --------------------------------------------------------- PC health
def _check_disk_health() -> None:
    try:
        usage = shutil.disk_usage(str(APP_DIR))
        if usage.total > 0:
            free_pct = usage.free / usage.total * 100.0
            if free_pct < 10.0:
                _warn_once_per_day(
                    "disk_low", "ডিস্ক প্রায় ভরে গেছে 💾",
                    f"ডিস্কে মাত্র {free_pct:.0f}% জায়গা খালি আছে — "
                    "কিছু পুরনো ফাইল মুছে জায়গা করলে ভালো হয়।")
    except Exception as e:
        _log(f"disk health যাচাই ব্যর্থ: {e!r}")


def _check_memory_health() -> None:
    if not _IS_WINDOWS:
        return
    try:
        class _MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

        stat = _MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        if kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            if int(stat.dwMemoryLoad) > 90:
                _warn_once_per_day(
                    "memory_high", "মেমরি প্রায় শেষ ⚠️",
                    f"RAM ব্যবহার {int(stat.dwMemoryLoad)}% — "
                    "ব্যবহার-না-করা app বন্ধ করলে PC হালকা হবে।")
    except Exception as e:
        _log(f"memory health যাচাই ব্যর্থ: {e!r}")


def _check_battery_health() -> None:
    if not _IS_WINDOWS:
        return
    try:
        class _SYSTEM_POWER_STATUS(ctypes.Structure):
            _fields_ = [("ACLineStatus", ctypes.c_byte),
                        ("BatteryFlag", ctypes.c_byte),
                        ("BatteryLifePercent", ctypes.c_byte),
                        ("SystemStatusFlag", ctypes.c_byte),
                        ("BatteryLifeTime", ctypes.c_ulong),
                        ("BatteryFullLifeTime", ctypes.c_ulong)]

        status = _SYSTEM_POWER_STATUS()
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        if kernel32.GetSystemPowerStatus(ctypes.byref(status)):
            ac_off = int(status.ACLineStatus) == 0
            pct = int(status.BatteryLifePercent)
            if ac_off and 0 <= pct <= 20:
                _warn_once_per_day(
                    "battery_low", "ব্যাটারি কম 🔋",
                    f"ব্যাটারি মাত্র {pct}% আর চার্জার লাগানো নেই — "
                    "এখনই চার্জার লাগাও, নইলে কাজ হারাতে পারে।")
    except Exception as e:
        _log(f"battery health যাচাই ব্যর্থ: {e!r}")


def _health_loop() -> None:
    """প্রতি ৬০ সেকেন্ডে disk / RAM / battery যাচাই (সতর্কতা দিনে একবার)।"""
    while not _quit_event.is_set():
        if _quit_event.wait(60.0):
            break
        for check in (_check_disk_health, _check_memory_health,
                      _check_battery_health):
            try:
                check()
            except Exception as e:
                _log(f"health check ব্যর্থ: {e!r}")


# --------------------------------------------------------- eye break
def _eye_break_loop() -> None:
    """প্রতি ১২০০ সেকেন্ডে (২০ মিনিট) চোখের বিরতির মনে করানো।"""
    while not _quit_event.is_set():
        if _quit_event.wait(1200.0):
            break
        try:
            if _setting("eye_break_on"):
                show_toast("চোখের বিরতি 👀",
                           "২০ সেকেন্ড দূরের কিছুতে তাকাও — "
                           "20-20-20 নিয়ম।")
        except Exception as e:
            _log(f"eye break toast ব্যর্থ: {e!r}")


# --------------------------------------------------------- clipboard
def _read_clipboard_text_windows():
    """CF_UNICODETEXT পড়া (ctypes) — Windows ছাড়া/ব্যর্থ হলে None।"""
    if not _IS_WINDOWS:
        return None
    user32 = ctypes.windll.user32      # type: ignore[attr-defined]
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    CF_UNICODETEXT = 13
    try:
        user32.GetClipboardData.restype = ctypes.c_void_p
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalSize.restype = ctypes.c_size_t
    except Exception:
        pass
    opened = False
    handle = None
    ptr = None
    try:
        if not user32.OpenClipboard(None):
            return None
        opened = True
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return None
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            return None
        try:
            size = int(kernel32.GlobalSize(handle))
        except Exception:
            size = 0
        if size and size >= 2:
            raw = ctypes.string_at(ptr, size)
            text = raw.decode("utf-16le", errors="ignore")
            return text.rstrip("\x00")
        return ctypes.wstring_at(ptr)
    except Exception as e:
        _log(f"clipboard পড়া ব্যর্থ: {e!r}")
        return None
    finally:
        try:
            if ptr and handle:
                kernel32.GlobalUnlock(handle)
        except Exception:
            pass
        try:
            if opened:
                user32.CloseClipboard()
        except Exception:
            pass


def _clipboard_loop() -> None:
    """শুধু Windows: লম্বা নতুন লেখা কপি হলে (সর্বোচ্চ ১০ মিনিটে একবার)
    সেভ + toast। Poll প্রতি ১.৫ সেকেন্ড।"""
    global _last_clipboard_hash, _last_clipboard_toast_at
    if not _IS_WINDOWS:
        _log("clipboard-নজর শুধু Windows-এ — এই সিস্টেমে skip।")
        return
    while not _quit_event.is_set():
        if _quit_event.wait(1.5):
            break
        try:
            if not _setting("clipboard_on"):
                continue
            text = _read_clipboard_text_windows()
            if not text:
                continue
            if len(text) < 40 or " " not in text:
                continue
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            if digest == _last_clipboard_hash:
                continue
            _last_clipboard_hash = digest
            now = time.time()
            if now - _last_clipboard_toast_at < 600.0:
                continue
            _last_clipboard_toast_at = now
            try:
                DATA_DIR.mkdir(parents=True, exist_ok=True)
                CLIPBOARD_FILE.write_text(text, encoding="utf-8")
            except Exception as e:
                _log(f"clipboard_last.txt লেখা গেল না: {e!r}")
            show_toast("ক্লিপবোর্ড 📋",
                       "নতুন লেখা কপি হয়েছে — Sokhi-তে বলো "
                       "'ক্লিপবোর্ড বুঝাও'")
        except Exception as e:
            _log(f"clipboard watcher-এ ভুল: {e!r}")


# --------------------------------------------------------- auto-update
def _version_tuple(value) -> tuple:
    parts = []
    try:
        for piece in str(value or "0").strip().lstrip("vV").split("."):
            num = ""
            for ch in piece:
                if ch.isdigit():
                    num += ch
                else:
                    break
            parts.append(int(num) if num else 0)
    except Exception:
        return (0,)
    return tuple(parts) or (0,)


def _update_check_once() -> None:
    """চালুর ~৫ সেকেন্ড পর একবার manifest যাচাই — নতুন version থাকলে
    শুধু toast; নিজে কখনো কিছু download/install করে না।"""
    try:
        if _quit_event.wait(5.0):
            return
        update_url = ""
        try:
            if CONFIG_FILE.exists():
                cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                if isinstance(cfg, dict):
                    update_url = str(cfg.get("update_url") or "").strip()
        except Exception as e:
            _log(f"update যাচাই: config.json পড়া গেল না: {e!r}")
            return
        if not update_url:
            _log("update যাচাই: config.json-এ update_url নেই — skip।")
            return
        local_version = "0"
        try:
            if VERSION_FILE.exists():
                vraw = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
                if isinstance(vraw, dict):
                    local_version = str(vraw.get("version") or "0")
        except Exception as e:
            _log(f"update যাচাই: version.json পড়া গেল না: {e!r}")
        try:
            req = urllib.request.Request(
                update_url, headers={"User-Agent": "Sokhi-Launcher"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                manifest = json.loads(
                    resp.read().decode("utf-8", errors="replace"))
        except Exception as e:
            _log(f"update যাচাই: manifest আনা গেল না: {e!r}")
            return
        remote_version = ""
        if isinstance(manifest, dict):
            remote_version = str(manifest.get("version") or "").strip()
        if not remote_version:
            _log("update যাচাই: manifest-এ version নেই — skip।")
            return
        if _version_tuple(remote_version) > _version_tuple(local_version):
            if not _once_ever(f"update_notified:{remote_version}"):
                show_toast(
                    "নতুন আপডেট 🎉",
                    f"Sokhi v{remote_version} এসেছে — নিতে চাইলে "
                    "Sokhi-তে বলো 'আপগ্রেড চেক করো'। তোমার সম্মতি "
                    "ছাড়া কিছু বসবে না।")
            else:
                _log(f"update v{remote_version}-এর toast আগেই দেওয়া "
                     "হয়েছে — আবার নয়।")
        else:
            _log(f"update যাচাই: Sokhi হালনাগাদ আছে "
                 f"(local={local_version}, remote={remote_version})।")
    except Exception as e:
        _log(f"update যাচাই ব্যর্থ — বাকি app চলবে: {e!r}")


# -------------------------------------------------------------- explain
_EXPLAIN_SUFFIXES = {".txt", ".md", ".py", ".json", ".csv", ".log",
                     ".html"}
_EXPLAIN_MAX_BYTES = 200 * 1024
_EXPLAIN_MAX_CHARS = 4000


def _parse_explain_arg():
    """argv-তে --explain <path> থাকলে path, নইলে None।"""
    try:
        args = sys.argv[1:]
        if "--explain" in args:
            idx = args.index("--explain")
            if idx + 1 < len(args):
                return args[idx + 1]
            _log("--explain দেওয়া হয়েছে কিন্তু ফাইলের পথ নেই।")
    except Exception as e:
        _log(f"--explain খোঁজা ব্যর্থ: {e!r}")
    return None


def _do_explain(path_str: str) -> None:
    """ফাইলটা সার্ভারের /api/chat-এ পাঠিয়ে সহজ বাংলায় বোঝাতে বলা।
    এখানে শুধু অনুরোধ পাঠানো হয় — উত্তর Sokhi নিজে chat-এ দেখায়/
    বলে (উইন্ডো এর পরেই খোলে)। ভুল হলে log; app থামে না।"""
    try:
        path = Path(path_str)
        if not path.exists() or not path.is_file():
            msg = f"--explain: ফাইল পাওয়া গেল না: {path_str}"
            _log(msg)
            show_toast("Sokhi — ফাইল বোঝানো", msg)
            return
        try:
            size = path.stat().st_size
        except Exception:
            size = 0
        if path.suffix.lower() not in _EXPLAIN_SUFFIXES or \
                size >= _EXPLAIN_MAX_BYTES:
            msg = (f"এই ফাইলটা বোঝানো যাবে না (ধরন "
                   f"{path.suffix or 'অজানা'}, সাইজ {size} bytes) — "
                   "শুধু .txt/.md/.py/.json/.csv/.log/.html আর "
                   "200KB-র ছোট ফাইল হয়।")
            _log(f"--explain অসমর্থিত ফাইল: {path} — {msg}")
            show_toast("Sokhi — ফাইল বোঝানো", msg)
            return
        try:
            text = path.read_text(encoding="utf-8",
                                  errors="replace")[:_EXPLAIN_MAX_CHARS]
        except Exception as e:
            _log(f"--explain: ফাইল পড়া গেল না: {e!r}")
            return
        pin = ""
        try:
            if PIN_FILE.exists():
                pin = PIN_FILE.read_text(encoding="utf-8").strip()
        except Exception as e:
            _log(f"--explain: pin.txt পড়া গেল না: {e!r}")
        payload = json.dumps(
            {"message": "এই ফাইলটা সহজ বাংলায় বুঝিয়ে দাও:\n\n" + text},
            ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if pin:
            headers["X-PIN"] = pin
        req = urllib.request.Request(URL + "/api/chat", data=payload,
                                     headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = resp.read().decode("utf-8", errors="replace")
            _log(f"--explain পাঠানো হলো ({path.name}) — সার্ভারের জবাব: "
                 f"{body[:300]}")
        except Exception as e:
            _log(f"--explain: /api/chat-এ পাঠানো ব্যর্থ: {e!r}")
    except Exception as e:
        _log(f"--explain ব্যর্থ — উইন্ডো স্বাভাবিকভাবেই খুলবে: {e!r}")


# ------------------------------------------------- background services
def _start_background_services() -> None:
    """সব নতুন পেছনের সেবা — একেকটা আলাদাভাবে, একটা ভাঙলে বাকিগুলো চলে।"""
    starters = []
    try:
        starters.append(
            ("toast watcher",
             lambda: threading.Thread(target=_toast_watcher_loop,
                                      name="sokhi-toast",
                                      daemon=True).start()))
    except Exception:
        pass
    starters.append(("tray", _start_tray))
    starters.append(
        ("hotkey",
         lambda: threading.Thread(target=_hotkey_loop,
                                  name="sokhi-hotkey",
                                  daemon=True).start()))
    starters.append(
        ("PC health",
         lambda: threading.Thread(target=_health_loop,
                                  name="sokhi-health",
                                  daemon=True).start()))
    starters.append(
        ("eye break",
         lambda: threading.Thread(target=_eye_break_loop,
                                  name="sokhi-eye",
                                  daemon=True).start()))
    starters.append(
        ("clipboard",
         lambda: threading.Thread(target=_clipboard_loop,
                                  name="sokhi-clipboard",
                                  daemon=True).start()))
    starters.append(
        ("update check",
         lambda: threading.Thread(target=_update_check_once,
                                  name="sokhi-update",
                                  daemon=True).start()))
    for name, starter in starters:
        try:
            starter()
        except Exception as e:
            _log(f"background সেবা চালু ব্যর্থ ({name}) — বাকিগুলো "
                 f"চলবে: {e!r}")


# ----------------------------------------------------------------- server
_server_error = {}
_orig_browser_open = webbrowser.open


def _run_server_thread() -> None:
    """sokhi.py-কে এই process-এর thread-এ চালায়। sokhi.py শুরুতেই
    webbrowser.open() দিয়ে browser খোলে — app মোডে সেটা চাই না, তাই
    সার্ভার ওঠা পর্যন্ত webbrowser.open সাময়িকভাবে চুপ করিয়ে রাখি
    (port জবাব দিলেই main thread আসলটা ফিরিয়ে দেয়; পরে chat থেকে
    'YouTube খোলো' জাতীয় কমান্ডে browser আগের মতোই খুলবে)।"""

    def _swallow(*a, **k):
        return True

    webbrowser.open = _swallow
    try:
        runpy.run_path(str(SOKHI_PY), run_name="__main__")
    except SystemExit as e:  # sokhi.py নিজে exit ডাকলে
        _server_error["exit"] = e.code
    except BaseException as e:  # আসল ভুল — লুকোবো না, log-এ থাকবে
        _server_error["error"] = repr(e)
        _log(f"sokhi.py চালাতে গিয়ে ভুল: {e!r}")


def server_up(timeout: float = 0.6) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=timeout):
            return True
    except OSError:
        return False


def wait_for_server(timeout_s: float = 90.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if _server_error:
            return False
        if server_up(0.5):
            return True
        time.sleep(0.25)
    return server_up(1.0)


# ----------------------------------------------------------------- window
def _splash_logo_html() -> str:
    """sokhi.png (APP_DIR বা frozen হলে sys._MEIPASS) পেলে base64 <img>,
    নইলে CSS orb।"""
    try:
        candidates = [PNG_FILE]
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.insert(0, Path(meipass) / "sokhi.png")
        for cand in candidates:
            try:
                if cand.exists():
                    b64 = base64.b64encode(cand.read_bytes()).decode("ascii")
                    return (f'<img src="data:image/png;base64,{b64}" '
                            'alt="Sokhi" style="width:110px;height:110px;'
                            'object-fit:contain;animation:p 1.6s '
                            'ease-in-out infinite">')
            except Exception as e:
                _log(f"splash-এর জন্য sokhi.png পড়া গেল না: {e!r}")
    except Exception as e:
        _log(f"splash logo বানানো ব্যর্থ, CSS orb যাচ্ছে: {e!r}")
    return '<div class="orb"></div>'


def _build_splash_html() -> str:
    logo = _splash_logo_html()
    return f"""<!doctype html>
<html lang="bn"><head><meta charset="utf-8">
<title>Sokhi</title>
<style>
  body{{margin:0;height:100vh;display:flex;flex-direction:column;gap:14px;
       align-items:center;justify-content:center;background:#0d1330;
       color:#e8ecff;font-family:'Hind Siliguri','Nirmala UI',sans-serif}}
  .orb{{width:92px;height:92px;border-radius:50%;
       background:radial-gradient(circle at 35% 30%,#a5f3fc,#38bdf8 45%,#8b5cf6 100%);
       box-shadow:0 0 44px #38bdf888;animation:p 1.6s ease-in-out infinite}}
  @keyframes p{{0%,100%{{transform:scale(1)}}50%{{transform:scale(1.07)}}}}
  h1{{font-size:22px;margin:0;font-weight:600}}
  p{{margin:0;opacity:.75;font-size:15px;text-align:center;padding:0 24px}}
  p.small{{font-size:13px;opacity:.55}}
</style></head>
<body>{logo}<h1>Sokhi</h1>
<p>তোমার নিজের AI সঙ্গী — সম্পূর্ণ ফ্রি, তোমার PC-তেই</p>
<p class="small">Sokhi চালু হচ্ছে…</p></body></html>"""


try:
    SPLASH_HTML = _build_splash_html()
except Exception:
    SPLASH_HTML = """<!doctype html>
<html lang="bn"><head><meta charset="utf-8">
<title>Sokhi</title>
<style>
  body{margin:0;height:100vh;display:flex;flex-direction:column;gap:14px;
       align-items:center;justify-content:center;background:#0d1330;
       color:#e8ecff;font-family:'Hind Siliguri','Nirmala UI',sans-serif}
  .orb{width:92px;height:92px;border-radius:50%;
       background:radial-gradient(circle at 35% 30%,#a5f3fc,#38bdf8 45%,#8b5cf6 100%);
       box-shadow:0 0 44px #38bdf888;animation:p 1.6s ease-in-out infinite}
  @keyframes p{0%,100%{transform:scale(1)}50%{transform:scale(1.07)}}
  h1{font-size:22px;margin:0;font-weight:600}
  p{margin:0;opacity:.75;font-size:15px}
</style></head>
<body><div class="orb"></div><h1>Sokhi</h1>
<p>তোমার নিজের AI সঙ্গী — সম্পূর্ণ ফ্রি, তোমার PC-তেই</p></body></html>"""


def _load_when_ready(window) -> None:
    for _ in range(160):  # সর্বোচ্চ ~40 সেকেন্ড
        if server_up(0.5):
            break
        time.sleep(0.25)
    try:
        window.load_url(URL)
    except Exception as e:
        _log(f"উইন্ডোতে পেজ লোড ব্যর্থ: {e!r}")


def _open_pywebview() -> bool:
    global _main_window, _webview_mod
    try:
        import webview
    except Exception:
        return False
    _webview_mod = webview
    try:
        window = webview.create_window(
            APP_NAME, html=SPLASH_HTML, js_api=_api, width=1280,
            height=860, min_size=(900, 600))
        _main_window = window
        # Close/Minimize = বন্ধ নয়, tray-তে hide (quit শুধু tray থেকে)
        try:
            window.events.closing += _on_main_closing
        except Exception as e:
            _log(f"closing event বাঁধা গেল না: {e!r}")
        try:
            window.events.minimized += _on_main_minimized
        except Exception as e:
            _log(f"minimized event বাঁধা গেল না: {e!r}")
        # ভাসমান ছোট্ট Sokhi (mini_on হলে)
        try:
            if _setting("mini_on"):
                _create_mini_window()
        except Exception as e:
            _log(f"mini window বানানো গেল না — main চলবে: {e!r}")
        threading.Thread(target=_load_when_ready, args=(window,),
                         daemon=True).start()
        webview.start()  # উইন্ডো (লুকানো হলেও) চলা পর্যন্ত এখানেই থাকে
        return True
    except Exception as e:
        _log(f"pywebview উইন্ডো ব্যর্থ, fallback-এ যাচ্ছি: {e!r}")
        return False


def _find_app_browser() -> str | None:
    """Edge/Chrome-এর exe খোঁজে (--app মোডের জন্য)।"""
    for name in ("msedge", "msedge.exe", "chrome", "chrome.exe",
                 "google-chrome", "chromium"):
        p = shutil.which(name)
        if p:
            return p
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    pfx = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    for base in (pfx, pf):
        for rel in (r"Microsoft\Edge\Application\msedge.exe",
                    r"Google\Chrome\Application\chrome.exe"):
            cand = Path(base) / rel
            if cand.exists():
                return str(cand)
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        cand = Path(local) / r"Google\Chrome\Application\chrome.exe"
        if cand.exists():
            return str(cand)
    return None


def _keep_alive_until_server_dies(thread: threading.Thread | None) -> None:
    """Browser-fallback মোডে সার্ভার আমাদের process-এই থাকে — launcher
    বেঁচে না থাকলে Sokhi-ও বন্ধ। তাই সার্ভার-thread শেষ না হওয়া
    পর্যন্ত (বা tray থেকে quit flag এলে) অপেক্ষা। (pywebview মোডে
    এই পথ লাগে না।)"""
    try:
        while not _quit_event.is_set():
            if thread is not None and not thread.is_alive():
                break
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass


def open_window(server_thread: threading.Thread | None,
                we_started_server: bool) -> bool:
    # ১) নিজের আসল উইন্ডো (pywebview)
    if _open_pywebview():
        return True
    # Fallback মোডেও tray চলতে থাকে (আগেই চালু হয়েছে) — keep-alive
    # loop _quit_event দেখে, tray থেকে "সম্পূর্ণ বন্ধ করো" দিলেই থামে।
    keep_alive = we_started_server or _tray_icon is not None
    # ২) Edge/Chrome --app মোড (ট্যাব/অ্যাড্রেস বার ছাড়া)
    exe = _find_app_browser()
    if exe:
        try:
            subprocess.Popen([exe, f"--app={URL}",
                              "--window-size=1280,860"])
            _log(f"browser --app মোডে খোলা হলো: {exe}")
            if keep_alive:
                _keep_alive_until_server_dies(server_thread)
            return True
        except Exception as e:
            _log(f"--app মোড ব্যর্থ: {e!r}")
    # ৩) সাধারণ browser
    try:
        if _orig_browser_open(URL):
            _log("সাধারণ browser-এ খোলা হলো")
            if keep_alive:
                _keep_alive_until_server_dies(server_thread)
            return True
    except Exception as e:
        _log(f"browser খোলা ব্যর্থ: {e!r}")
    return False


# ------------------------------------------------------------------- main
def main() -> int:
    _stdio_to_log()
    # --explain <path>: mux-এর বাইরে, main-এর একদম শুরুতে ধরা হয়;
    # আসল কাজটা সার্ভার ওঠার পর (_do_explain)।
    explain_path = _parse_explain_arg()
    try:
        _load_settings()
    except Exception as e:
        _log(f"settings লোড ব্যর্থ — default দিয়ে চলছি: {e!r}")
    try:
        _start_background_services()
    except Exception as e:
        _log(f"background সেবা চালুতে ভুল — মূল app চলবে: {e!r}")

    if not SOKHI_PY.exists():
        _log(f"sokhi.py পাওয়া যাচ্ছে না: {SOKHI_PY} — "
             "Sokhi.exe অবশ্যই sokhi.py-র পাশের ফোল্ডারেই থাকতে হবে।")
        return 2

    server_thread = None
    we_started = False
    if server_up(0.8):
        _log("সার্ভার আগেই চলছে — দ্বিতীয় কপি নয়, শুধু উইন্ডো খুলছি।")
    else:
        server_thread = threading.Thread(target=_run_server_thread,
                                         name="sokhi-server", daemon=True)
        server_thread.start()
        we_started = True
        if not wait_for_server():
            _log(f"সার্ভার উঠল না। ত্রুটি: {_server_error or 'অজানা'} — "
                 f"বিস্তারিত: {LOG_FILE}")
            return 3
        # সার্ভার উঠে গেছে মানে sokhi.py-র শুরুর webbrowser.open ইতিমধ্যে
        # পেরিয়ে গেছে — আসল webbrowser.open ফিরিয়ে দিই (chat কমান্ডের জন্য)।
        webbrowser.open = _orig_browser_open
        _log(f"সার্ভার চালু: {URL}")

    # সার্ভার তৈরি — এখন --explain-এর ফাইলটা Sokhi-কে বোঝাতে পাঠাই,
    # তারপর স্বাভাবিক উইন্ডো-প্রবাহ।
    if explain_path:
        try:
            _do_explain(explain_path)
        except Exception as e:
            _log(f"--explain সামলাতে ভুল: {e!r}")

    ok = open_window(server_thread, we_started)
    if not ok:
        _log("কোনো উইন্ডোই খোলা গেল না — সার্ভার চালু রেখে অপেক্ষা করছি; "
             f"browser-এ {URL} খুললেই Sokhi পাবে।")
        if we_started:
            _keep_alive_until_server_dies(server_thread)
        return 4
    _log("উইন্ডো বন্ধ — Sokhi বন্ধ হচ্ছে।")
    return 0


if __name__ == "__main__":
    if _mux_if_needed():
        sys.exit(0)  # mux ভেতরেই exit করেছে; এখানে পৌঁছানোর কথা নয়
    code = 0
    try:
        code = main()
    except Exception as e:
        _log(f"অপ্রত্যাশিত ভুল: {e!r}")
        code = 1
    # daemon server-thread যেন ঝুলে না থাকে — process এখানেই শেষ
    os._exit(code)
