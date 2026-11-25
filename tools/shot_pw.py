# -*- coding: utf-8 -*-
"""按窗口标题/进程名用 PrintWindow 抓图（被其他窗口遮挡也能抓）。

用法：python tools/shot_pw.py <输出路径> [标题关键字]
"""
import ctypes
import ctypes.wintypes as wt
import sys

from PIL import Image

u = ctypes.windll.user32
g = ctypes.windll.gdi32


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class BIH(ctypes.Structure):
    _fields_ = [("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32),
                ("biHeight", ctypes.c_int32), ("biPlanes", ctypes.c_uint16),
                ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
                ("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_int32),
                ("biYPelsPerMeter", ctypes.c_int32), ("biClrUsed", ctypes.c_uint32),
                ("biClrImportant", ctypes.c_uint32)]


class BI(ctypes.Structure):
    _fields_ = [("bmiHeader", BIH), ("bmiColors", ctypes.c_uint32 * 3)]


def grab(hwnd, r, out):
    w, h = r.right - r.left, r.bottom - r.top
    hdc = u.GetWindowDC(hwnd)
    mem = g.CreateCompatibleDC(hdc)
    bmp = g.CreateCompatibleBitmap(hdc, w, h)
    g.SelectObject(mem, bmp)
    u.PrintWindow(hwnd, mem, 2)

    bi = BI()
    bi.bmiHeader.biSize = ctypes.sizeof(BIH)
    bi.bmiHeader.biWidth = w
    bi.bmiHeader.biHeight = -h
    bi.bmiHeader.biPlanes = 1
    bi.bmiHeader.biBitCount = 32
    buf = ctypes.create_string_buffer(w * h * 4)
    g.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(bi), 0)
    img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB")
    img.save(out)
    g.DeleteObject(bmp)
    g.DeleteDC(mem)
    u.ReleaseDC(hwnd, hdc)
    return img


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "docs/ui_progress.png"
    want = sys.argv[2] if len(sys.argv) > 2 else "Welearn"
    hits = []

    def cb(hwnd, _l):
        if not u.IsWindowVisible(hwnd):
            return True
        b = ctypes.create_unicode_buffer(256)
        u.GetWindowTextW(hwnd, b, 256)
        if want in b.value:
            r = RECT()
            u.GetWindowRect(hwnd, ctypes.byref(r))
            if r.right - r.left > 300:
                hits.append((hwnd, b.value, r))
        return True

    u.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)(cb), 0)
    if not hits:
        print("no window")
        sys.exit(1)
    hwnd, title, r = max(hits, key=lambda x: (x[2].bottom - x[2].top))
    img = grab(hwnd, r, out)
    print("saved", out, img.size, "|", title)
