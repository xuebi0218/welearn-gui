# -*- coding: utf-8 -*-
"""v4.1 补丁 25：真彩渐变圆角进度条（PIL 渲染 + Canvas 承载 + 平滑动画）。

CTkProgressBar 只能单色填充，这里自己画：
- 轨道：圆角深色，带 1px 内描边
- 填充：青 → 靛 → 紫 三段渐变，右端胶囊圆头
- 细节：顶部高光、末端光点、可选节数刻度
- 动画：数值变化 260ms 缓出补间，不再生硬跳变
"""
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


# ── 1. 依赖 ──
rep("""import customtkinter as ctk
from PIL import Image
from tkinter import messagebox""",
    """import customtkinter as ctk
import tkinter as tk
from PIL import Image, ImageDraw, ImageTk
from tkinter import messagebox""")

# ── 2. 渐变条组件 ──
BAR_CLASS = '''

def _hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _mix(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def _gradient_stops(colors, n):
    """把若干色标均匀插值成 n 段 RGB 列表。"""
    cols = [_hex_rgb(c) for c in colors]
    out = []
    seg = len(cols) - 1
    for i in range(n):
        t = i / max(1, n - 1) * seg
        k = min(seg - 1, int(t))
        out.append(_mix(cols[k], cols[k + 1], t - k))
    return out


class GradientBar(tk.Canvas):
    """圆角渐变进度条：轨道 + 渐变填充 + 高光 + 末端光点。"""

    TRACK = {"dark": "#16233c", "light": "#e6edf7"}
    EDGE = {"dark": "#22355a", "light": "#d2dcec"}
    BG = {"dark": "#0d1626", "light": "#ffffff"}

    def __init__(self, master, width=380, height=12, radius=None,
                 colors=("#4cc9d6", "#5b8def", "#8b7cf0"), value=0.0,
                 ticks=None, animate=True, bg=None, **kw):
        self._h = int(height)
        self._w = int(width)
        self._r = int(radius if radius else height / 2)
        self._colors = colors
        self._animate = animate
        self._target = max(0.0, min(1.0, float(value)))
        self._cur = self._target
        self._ticks = ticks
        self._img = None
        self._anim_job = None
        mode = ctk.get_appearance_mode().lower()
        bgc = bg or self.BG.get(mode, "#0d1626")
        super().__init__(master, width=self._w, height=self._h,
                         bg=bgc, highlightthickness=0, bd=0, **kw)
        self._bgc = bgc
        self.bind("<Configure>", self._on_conf)
        self.after(30, self._render)

    # ── 对外接口，与 CTkProgressBar 保持一致 ──
    def set(self, value, animate=None):
        value = max(0.0, min(1.0, float(value)))
        self._target = value
        if animate is None:
            animate = self._animate
        if not animate or abs(value - self._cur) < 0.001:
            self._cur = value
            self._render()
            return
        self._animate_to(value)

    def get(self):
        return self._cur

    def set_ticks(self, n):
        """按节数在条上画刻度（n<=48 才画，太密就不画了）。"""
        self._ticks = n if (n and 1 < n <= 48) else None
        self._render()

    def set_bg(self, color):
        self._bgc = color
        self.configure(bg=color)
        self._render()

    # ── 动画 ──
    def _animate_to(self, target):
        if self._anim_job:
            try:
                self.after_cancel(self._anim_job)
            except Exception:
                pass
        start = self._cur
        steps = 14
        i = [0]

        def _step():
            i[0] += 1
            t = i[0] / steps
            ease = 1 - (1 - t) ** 3          # ease-out cubic
            self._cur = start + (target - start) * ease
            self._render()
            if i[0] < steps:
                self._anim_job = self.after(16, _step)
            else:
                self._cur = target
                self._anim_job = None
                self._render()

        self._anim_job = self.after(16, _step)

    # ── 绘制 ──
    def _on_conf(self, event):
        if event.width > 8 and abs(event.width - self._w) > 2:
            self._w = event.width
            self._render()

    def _render(self):
        try:
            w, h, r = max(8, self._w), max(4, self._h), self._r
            mode = ctk.get_appearance_mode().lower()
            img = Image.new("RGBA", (w, h), _hex_rgb(self._bgc) + (255,))
            d = ImageDraw.Draw(img)

            # 轨道
            d.rounded_rectangle((0, 0, w - 1, h - 1), radius=r,
                                fill=_hex_rgb(self.TRACK.get(mode, "#16233c")) + (255,),
                                outline=_hex_rgb(self.EDGE.get(mode, "#22355a")) + (255,),
                                width=1)

            # 填充
            fw = int(round(w * self._cur))
            if fw >= 2:
                fw = max(fw, min(w, h))
                stops = _gradient_stops(self._colors, fw)
                bar = Image.new("RGBA", (fw, h - 2), (0, 0, 0, 0))
                bd = ImageDraw.Draw(bar)
                for x in range(fw):
                    bd.line([(x, 0), (x, h - 3)], fill=stops[x] + (255,))
                mask = Image.new("L", (fw, h - 2), 0)
                ImageDraw.Draw(mask).rounded_rectangle(
                    (0, 0, fw - 1, h - 3), radius=max(1, r - 1), fill=255)
                img.paste(bar, (1, 1), mask)

                # 顶部高光
                hl = Image.new("RGBA", (fw, h - 2), (0, 0, 0, 0))
                hd = ImageDraw.Draw(hl)
                hd.rounded_rectangle((0, 0, fw - 1, max(1, (h - 2) // 2)), radius=r,
                                     fill=(255, 255, 255, 46))
                img.paste(Image.composite(hl, Image.new("RGBA", hl.size, (0, 0, 0, 0)), mask),
                          (1, 1), mask)

                # 末端光点
                if fw > h and self._cur < 0.995:
                    cx, cy = fw, h // 2
                    rr = max(1.6, (h - 4) / 2)
                    d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr),
                              fill=(235, 250, 255, 235))

            # 节数刻度
            if self._ticks:
                for i in range(1, self._ticks):
                    x = 1 + int((w - 2) * i / self._ticks)
                    filled = (x <= int(w * self._cur))
                    d.line([(x, 2), (x, h - 3)],
                           fill=(255, 255, 255, 60) if filled else (120, 140, 170, 46))

            self._img = ImageTk.PhotoImage(img)
            self.delete("all")
            self.create_image(0, 0, anchor="nw", image=self._img)
        except Exception:
            pass


'''

rep("""# ── 常量 ──────────────────────────────────────────────""",
    "# ── 渐变进度条组件 ────────────────────────────────────" + BAR_CLASS + """# ── 常量 ──────────────────────────────────────────────""")

# ── 3. 总进度条换掉 ──
rep("""        self.task_progress_bar = ctk.CTkProgressBar(progress_frame, height=10, corner_radius=5,
                                                    progress_color=("#4cc9d6", "#5b8def"))
        self.task_progress_bar.pack(fill="x", padx=14, pady=(4, 8))
        self.task_progress_bar.set(0)""",
    """        self.task_progress_bar = GradientBar(progress_frame, width=520, height=12,
                                             radius=6, animate=True)
        self.task_progress_bar.pack(fill="x", padx=14, pady=(6, 8))""")

# ── 4. 每路单节条换掉 ──
rep("""        bar = ctk.CTkProgressBar(row, width=104, height=6, corner_radius=3,
                                 progress_color=("#4cc9d6", "#5b8def"))
        bar.pack(side="left")
        bar.set(0)""",
    """        bar = GradientBar(row, width=104, height=7, radius=3, animate=True)
        bar.pack(side="left")""")

open(P, "w", encoding="utf-8").write(src)
print("patch25 ok")
