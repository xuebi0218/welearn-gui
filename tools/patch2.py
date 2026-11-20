# -*- coding: utf-8 -*-
"""v3.6 补丁 2：吉祥物 nobi → 大肥鱼鲸鱼娘（dsh-pet 素材）。"""
import sys

P = "src/welearn_gui.py"
src = open(P, encoding="utf-8").read()


def rep(old, new, cnt=1):
    global src
    n = src.count(old)
    if n != cnt:
        print("MISMATCH(%d):" % n, old[:70].replace("\n", "\\n"))
        sys.exit(1)
    src = src.replace(old, new)


# 1) 资源路径
rep('''    _DONATE_QR_PATH = _os.path.join(sys._MEIPASS, 'src', 'donate_qr.jpg')
    _NOBI_PATH = _os.path.join(sys._MEIPASS, 'src', 'nobi.png')
else:
    _DONATE_QR_PATH = _os.path.join(_SRC_DIR, 'donate_qr.jpg')
    _NOBI_PATH = _os.path.join(_SRC_DIR, 'nobi.png')''',
    '''    _DONATE_QR_PATH = _os.path.join(sys._MEIPASS, 'src', 'donate_qr.jpg')
    _MASCOT_PATH = _os.path.join(sys._MEIPASS, 'src', 'mascot.png')
else:
    _DONATE_QR_PATH = _os.path.join(_SRC_DIR, 'donate_qr.jpg')
    _MASCOT_PATH = _os.path.join(_SRC_DIR, 'mascot.png')

MASCOT_NAME = "大肥鱼鲸鱼娘"''')

# 2) 侧边栏吉祥物卡片
rep('''        # ── IP 吉祥物 ──
        mascot_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        mascot_frame.pack(fill="x", padx=20, pady=(18, 2))
        try:
            nobi_img = ctk.CTkImage(Image.open(_NOBI_PATH), size=(54, 54))
            ctk.CTkLabel(mascot_frame, image=nobi_img, text="").pack(anchor="center")
        except Exception:
            ctk.CTkLabel(mascot_frame, text="🐰", font=ctk.CTkFont(size=32)).pack(anchor="center")
        ctk.CTkLabel(mascot_frame, text="Welearn",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=("#e2e8f0", "#e2e8f0")).pack(anchor="center", pady=(4, 0))
        ctk.CTkLabel(mascot_frame, text="刷课工具",
                     font=ctk.CTkFont(size=9),
                     text_color=("#f0abfc", "#c084fc")).pack(anchor="center", pady=(1, 0))''',
    '''        # ── IP 吉祥物：大肥鱼鲸鱼娘 ──
        mascot_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        mascot_frame.pack(fill="x", padx=20, pady=(16, 2))
        try:
            self._mascot_img = ctk.CTkImage(Image.open(_MASCOT_PATH), size=(104, 104))
            mascot_badge = ctk.CTkFrame(mascot_frame, corner_radius=52,
                                        fg_color=("#eef2ff", "#111a33"),
                                        border_width=1, border_color=("#c7d2fe", "#2c3e6b"))
            mascot_badge.pack(anchor="center")
            ctk.CTkLabel(mascot_badge, image=self._mascot_img, text="").pack(padx=8, pady=8)
        except Exception:
            ctk.CTkLabel(mascot_frame, text="🐳", font=ctk.CTkFont(size=48)).pack(anchor="center")
        ctk.CTkLabel(mascot_frame, text=MASCOT_NAME,
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=("#1e3a8a", "#dbe4ff")).pack(anchor="center", pady=(8, 0))
        ctk.CTkLabel(mascot_frame, text="Welearn 刷课助手",
                     font=ctk.CTkFont(size=10),
                     text_color=("#64748b", "#7c8db5")).pack(anchor="center", pady=(1, 0))''')

# 3) 版本号
src = src.replace('v3.5 · 免费开源', 'v3.6 · 免费开源')

open(P, "w", encoding="utf-8").write(src)
print("patch2 ok")
