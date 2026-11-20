# -*- coding: utf-8 -*-
"""v3.8 补丁：IP 动效 + 渐变横幅 + 去角色名 + 深海配色统一。"""
import sys

P = "src/welearn_gui.py"
src = open(P, encoding="utf-8").read()


def rep(old, new, cnt=1):
    global src
    n = src.count(old)
    if n != cnt:
        print("MISMATCH(%d):" % n, old[:90].replace("\n", "\\n"))
        sys.exit(1)
    src = src.replace(old, new)


# ── 1. 资源路径：动效帧 + 横幅 ──
rep('''MASCOT_NAME = "大肥鱼鲸鱼娘"''',
    '''_ANIM_FRAMES = [f"anim_{i}.png" for i in range(6)]


def _asset(name):
    """打包后从 _MEIPASS 取，开发时从 src/ 取。"""
    base = getattr(sys, '_MEIPASS', None)
    if base:
        return _os.path.join(base, 'src', name)
    return _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), name)''')

# ── 2. 侧边栏：去掉名字/副标题，改成循环动效 ──
rep('''        # ── IP 吉祥物：大肥鱼鲸鱼娘 ──
        mascot_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        mascot_frame.pack(fill="x", padx=20, pady=(16, 2))
        try:
            self._mascot_img = ctk.CTkImage(Image.open(_MASCOT_PATH), size=(104, 104))
            mascot_badge = ctk.CTkFrame(mascot_frame, corner_radius=26,
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
                     text_color=("#64748b", "#7c8db5")).pack(anchor="center", pady=(1, 0))''',
    '''        # ── 侧边栏立绘：循环播放的 idle 动效（不标注角色名） ──
        mascot_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        mascot_frame.pack(fill="x", padx=20, pady=(18, 4))
        try:
            badge = ctk.CTkFrame(mascot_frame, corner_radius=28,
                                 fg_color=("#e8eefc", "#0e1730"),
                                 border_width=1, border_color=("#b9c8f2", "#26406f"))
            badge.pack(anchor="center")
            self._anim_imgs = []
            for name in _ANIM_FRAMES:
                p = _asset(name)
                if _os.path.exists(p):
                    self._anim_imgs.append(ctk.CTkImage(Image.open(p), size=(112, 112)))
            self._mascot_img = self._anim_imgs[0] if self._anim_imgs else None
            self.mascot_label = ctk.CTkLabel(badge, image=self._mascot_img, text="")
            self.mascot_label.pack(padx=8, pady=8)
            if len(self._anim_imgs) > 1:
                self._anim_i = 0
                self.root.after(220, self._tick_mascot)
        except Exception:
            ctk.CTkLabel(mascot_frame, text="🐳", font=ctk.CTkFont(size=48)).pack(anchor="center")''')

# ── 3. 动效 tick ──
rep('''    # ═══ 侧边栏 ═══════════════════════════════════════''',
    '''    def _tick_mascot(self):
        """idle 动效：6 帧循环，运行中稍快一点（像在陪你干活）。"""
        try:
            self._anim_i = (self._anim_i + 1) % len(self._anim_imgs)
            self.mascot_label.configure(image=self._anim_imgs[self._anim_i])
        except Exception:
            return
        delay = 150 if getattr(self, "running", False) else 240
        self.root.after(delay, self._tick_mascot)

    # ═══ 侧边栏 ═══════════════════════════════════════''')

# ── 4. 主页顶部：渐变横幅（图 + 叠字，不用角色名） ──
rep('''        # ── 安全节奏卡片（v3.6）──''',
    '''        # ── 顶部渐变横幅 ──
        hero = ctk.CTkFrame(self.home_scroll, corner_radius=14, height=150,
                            fg_color=("transparent", "transparent"))
        hero.pack(fill="x", padx=10, pady=(6, 4))
        hero.pack_propagate(False)
        try:
            self._banner_img = ctk.CTkImage(Image.open(_asset("banner.png")), size=(760, 150))
            banner = ctk.CTkLabel(hero, image=self._banner_img, text="")
            banner.place(relx=0, rely=0, relwidth=1, relheight=1)
            banner.lower()
        except Exception:
            hero.configure(fg_color=("#16233f", "#101a30"))

        title_box = ctk.CTkFrame(hero, fg_color=("transparent", "transparent"))
        title_box.place(x=26, y=30)
        ctk.CTkLabel(title_box, text="WE·LEARN 学习助手",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=("#f2f7ff", "#e8f1ff")).pack(anchor="w")
        ctk.CTkLabel(title_box, text="按平台要求补齐学时 · 多路并行 · 提交后回读校验",
                     font=ctk.CTkFont(size=11),
                     text_color=("#a9c4e8", "#8fb0d8")).pack(anchor="w", pady=(4, 0))

        # ── 安全节奏卡片（v3.6）──''')

open(P, "w", encoding="utf-8").write(src)
print("patch16 ok")
