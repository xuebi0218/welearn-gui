# -*- coding: utf-8 -*-
"""抓取指定窗口的真实屏幕画面（PrintWindow 在这台机器上偶尔返回陈旧表面，改用屏幕抓取）。

用法：python tools/shot_scroll.py 0 [标题关键字]
"""
import ctypes
import ctypes.wintypes as wt
import sys
import time

from PIL import ImageGrab

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
STILL_ACTIVE = 259


def _alive(pid):
    h = kernel32.OpenProcess(0x1000, False, pid)
    if not h:
        return False
    code = ctypes.c_ulong()
    ok = kernel32.GetExitCodeProcess(h, ctypes.byref(code))
    kernel32.CloseHandle(h)
    return bool(ok) and code.value == STILL_ACTIVE


def find(want=""):
    hits = []

    def cb(hwnd, _l):
        if not user32.IsWindowVisible(hwnd):
            return True
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, buf, 256)
        if "Welearn" in buf.value and (not want or want in buf.value):
            wpid = wt.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
            if _alive(wpid.value):
                r = wt.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(r))
                if r.right - r.left > 300:
                    hits.append((hwnd, buf.value, r, wpid.value))
        return True

    user32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)(cb), 0)
    return hits


if __name__ == "__main__":
    want = sys.argv[2] if len(sys.argv) > 2 else ""
    hits = find(want)
    if not hits:
        print("no window")
        sys.exit(1)
    hwnd, title, r, pid = max(hits, key=lambda x: (x[2].bottom - x[2].top))
    user32.ShowWindow(hwnd, 9)
    try:
        user32.SetForegroundWindow(hwnd)
    except Exception:
        pass
    time.sleep(1.0)
    img = ImageGrab.grab(bbox=(r.left, r.top, r.right, r.bottom))
    out = "docs/ui_progress.png"
    img.convert("RGB").save(out)
    print("saved", out, img.size, "| pid", pid, title)
