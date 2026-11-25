# -*- coding: utf-8 -*-
"""把目标窗口临时置顶后用屏幕抓取（全屏游戏挡住时也能拍到）。

用法：python tools/shot_top.py <输出> [标题关键字]
"""
import ctypes
import ctypes.wintypes as wt
import sys
import time

from PIL import ImageGrab

u = ctypes.windll.user32
HWND_TOPMOST = -1
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_SHOWWINDOW = 0x0040


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "docs/ui_progress.png"
    want = sys.argv[2] if len(sys.argv) > 2 else "demo"
    hits = []

    def cb(hwnd, _l):
        if not u.IsWindowVisible(hwnd):
            return True
        b = ctypes.create_unicode_buffer(256)
        u.GetWindowTextW(hwnd, b, 256)
        if want in b.value:
            r = wt.RECT()
            u.GetWindowRect(hwnd, ctypes.byref(r))
            if r.right - r.left > 300:
                hits.append((hwnd, b.value, r))
        return True

    u.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)(cb), 0)
    if not hits:
        print("no window")
        sys.exit(1)
    hwnd, title, r = max(hits, key=lambda x: (x[2].bottom - x[2].top))
    u.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    u.ShowWindow(hwnd, 9)
    try:
        u.SetForegroundWindow(hwnd)
    except Exception:
        pass
    time.sleep(1.5)
    img = ImageGrab.grab(bbox=(r.left, r.top, r.right, r.bottom))
    img.convert("RGB").save(out)
    u.SetWindowPos(hwnd, -2, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)   # 取消置顶
    print("saved", out, img.size, "|", title)
