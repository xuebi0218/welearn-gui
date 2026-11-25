# -*- coding: utf-8 -*-
"""把应用窗口滚到指定位置并截图（用于核对进度区）。"""
import ctypes
import ctypes.wintypes as wt
import sys
import time

from PIL import Image

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


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


def find():
    hits = []

    def cb(h, _):
        if not user32.IsWindowVisible(h):
            return True
        b = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(h, b, 256)
        want = sys.argv[2] if len(sys.argv) > 2 else ""
        if "Welearn" in b.value and (not want or want in b.value):
            r = RECT()
            user32.GetWindowRect(h, ctypes.byref(r))
            if r.right - r.left > 300:
                pid = wt.DWORD()
            user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
            if _alive(pid.value):
                hits.append((h, b.value, r, pid.value))
        return True

    user32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)(cb), 0)
    return hits


cands = sorted(find(), key=lambda x: (x[2].bottom - x[2].top, x[2].right - x[2].left))
print("windows:", [(c[1], c[3]) for c in cands])
hwnd, title, r, pid = cands[-1]
user32.SetForegroundWindow(hwnd)
time.sleep(0.4)
# 鼠标移到内容区中间再滚轮
cx = r.left + (r.right - r.left) * 3 // 4
cy = r.top + (r.bottom - r.top) // 2
user32.SetCursorPos(int(cx), int(cy))
time.sleep(0.2)
# 先点一下内容区，让滚轮作用在对的控件上
user32.mouse_event(0x0002, 0, 0, 0, 0)   # LEFTDOWN
user32.mouse_event(0x0004, 0, 0, 0, 0)   # LEFTUP
time.sleep(0.3)
notches = int(sys.argv[1]) if len(sys.argv) > 1 else 0
for _ in range(abs(notches)):
    user32.mouse_event(0x0800, 0, 0, -120 if notches > 0 else 120, 0)
    time.sleep(0.03)
time.sleep(0.8)

w, h = r.right - r.left, r.bottom - r.top
hdc = user32.GetWindowDC(hwnd)
mem = gdi32.CreateCompatibleDC(hdc)
bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
gdi32.SelectObject(mem, bmp)
user32.PrintWindow(hwnd, mem, 2)


class BIH(ctypes.Structure):
    _fields_ = [("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32),
                ("biHeight", ctypes.c_int32), ("biPlanes", ctypes.c_uint16),
                ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
                ("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_int32),
                ("biYPelsPerMeter", ctypes.c_int32), ("biClrUsed", ctypes.c_uint32),
                ("biClrImportant", ctypes.c_uint32)]


class BI(ctypes.Structure):
    _fields_ = [("bmiHeader", BIH), ("bmiColors", ctypes.c_uint32 * 3)]


bi = BI()
bi.bmiHeader.biSize = ctypes.sizeof(BIH)
bi.bmiHeader.biWidth = w
bi.bmiHeader.biHeight = -h
bi.bmiHeader.biPlanes = 1
bi.bmiHeader.biBitCount = 32
buf = ctypes.create_string_buffer(w * h * 4)
gdi32.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(bi), 0)
img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB")
out = "docs/ui_progress.png"
img.save(out)
print("saved", out, img.size, "| pid", pid, title)
