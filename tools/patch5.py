# -*- coding: utf-8 -*-
"""v3.6 补丁 5：GUI 默认值/安全预设/校验/预计耗时/终态。"""
import re
import sys

P = "src/welearn_gui.py"
src = open(P, encoding="utf-8").read()


def rep(old, new, cnt=1):
    global src
    n = src.count(old)
    if n != cnt:
        print("MISMATCH(%d):" % n, old[:80].replace("\n", "\\n"))
        sys.exit(1)
    src = src.replace(old, new)


# ── 1. 文档头 + imports ──
rep('''v3.5: 修复最后一项卡住问题(join超时类型错误)、停止按钮即时响应(分段sleep+轮询join)、增强日志输出。
"""''',
    '''v3.5: 修复最后一项卡住问题(join超时类型错误)、停止按钮即时响应(分段sleep+轮询join)、增强日志输出。
v3.6: 按平台协议重写核心——自适应补齐课时时长、边学边心跳、提交后回读校验、
      isPausing/checkNoCaptcha 闸门检测、单并发、危险参数拦截、吉祥物换为大肥鱼鲸鱼娘。
"""''')

rep("import customtkinter as ctk\nfrom PIL import Image",
    "import customtkinter as ctk\nfrom PIL import Image\nfrom tkinter import messagebox")

# ── 2. 默认值 ──
rep('''        # 刷课参数
        self.curriculum_rate = 100
        self.curriculum_random = False
        self.curriculum_duration = [60, 120]
        self.curriculum_max_threads = 10

        # 刷时长参数
        self.time_duration = [60, 120]
        self.time_mode = 2
        self.time_max_threads = 10''',
    '''        # 刷课参数（v3.6 安全默认：正确率带随机、时长按平台要求补齐、单并发）
        self.curriculum_rate = [80, 92]
        self.curriculum_random = True
        self.curriculum_duration = [600, 900]
        self.curriculum_max_threads = 1

        # 刷时长参数
        self.time_duration = [600, 900]
        self.time_mode = 2
        self.time_max_threads = 1

        # 节奏与配额（防"短时间集中完成"被打回）
        self.risk_preset = "safe"
        self.daily_lesson_cap = 24
        self.cooldown_every = 4
        self.cooldown_range = (400, 900)''')

# ── 3. 主页顶部：安全节奏卡片 ──
rep('''        # ── 登录面板 ──
        self.login_frame = ctk.CTkFrame(self.home_scroll, corner_radius=12,''',
    '''        # ── 安全节奏卡片（v3.6）──
        self.risk_frame = ctk.CTkFrame(self.home_scroll, corner_radius=12,
                                       fg_color=("#fffbeb", "#241d10"),
                                       border_width=1,
                                       border_color=("#fde68a", "#6b5320"))
        self.risk_frame.pack(fill="x", padx=10, pady=(5, 3))

        head = ctk.CTkFrame(self.risk_frame, fg_color="transparent")
        head.pack(fill="x", padx=15, pady=(12, 2))
        ctk.CTkLabel(head, text="🛡 节奏与风险", font=ctk.CTkFont(size=15, weight="bold")
                     ).pack(side="left")
        self.preset_label = ctk.CTkLabel(head, text="", font=ctk.CTkFont(size=11),
                                         text_color=("#92400e", "#d6b370"))
        self.preset_label.pack(side="right")

        ctk.CTkLabel(self.risk_frame,
                     text="平台按「真实在线时长」计学时：单个课时通常要求 18 分钟，"
                          "脚本会自动补齐差额并在提交后回读校验。"
                          "被清记录的主因是「短时间集中完成」，所以默认单并发、单日上限、每几节休息一次。",
                     font=ctk.CTkFont(size=11), justify="left", wraplength=680,
                     text_color=("#78350f", "#c9b48a")
                     ).pack(anchor="w", padx=15, pady=(0, 8))

        preset_row = ctk.CTkFrame(self.risk_frame, fg_color="transparent")
        preset_row.pack(fill="x", padx=15, pady=(0, 6))
        self.preset_seg = ctk.CTkSegmentedButton(
            preset_row, values=["安全（推荐）", "标准", "极速"],
            command=self._on_preset_change, height=30)
        self.preset_seg.pack(side="left")
        self.preset_seg.set("安全（推荐）")
        ctk.CTkLabel(preset_row, text="   并发固定为 1（平台学习票据互斥，多线程会互相顶掉）",
                     font=ctk.CTkFont(size=10), text_color=("#92400e", "#a08a63")).pack(side="left")

        self.estimate_label = ctk.CTkLabel(self.risk_frame, text="", font=ctk.CTkFont(size=11),
                                           justify="left", text_color=("#78350f", "#c9b48a"))
        self.estimate_label.pack(anchor="w", padx=15, pady=(0, 12))

        # ── 登录面板 ──
        self.login_frame = ctk.CTkFrame(self.home_scroll, corner_radius=12,''')

# ── 4. 正确率默认改为随机 80~92 ──
rep('''        self.rate_var = ctk.StringVar(value="fixed")''',
    '''        self.rate_var = ctk.StringVar(value="random")''')
rep('''        self.fixed_rate_entry = ctk.CTkEntry(fixed_frame, width=65, placeholder_text="100")
        self.fixed_rate_entry.pack(side="left", padx=5)
        self.fixed_rate_entry.insert(0, "100")''',
    '''        self.fixed_rate_entry = ctk.CTkEntry(fixed_frame, width=65, placeholder_text="88")
        self.fixed_rate_entry.pack(side="left", padx=5)
        self.fixed_rate_entry.insert(0, "88")''')
rep('''        self.rand_min_entry = ctk.CTkEntry(rand_frame, width=55, placeholder_text="70")
        self.rand_min_entry.pack(side="left", padx=5)
        self.rand_min_entry.insert(0, "70")''',
    '''        self.rand_min_entry = ctk.CTkEntry(rand_frame, width=55, placeholder_text="80")
        self.rand_min_entry.pack(side="left", padx=5)
        self.rand_min_entry.insert(0, "80")''')
rep('''        self.rand_max_entry = ctk.CTkEntry(rand_frame, width=55, placeholder_text="100")
        self.rand_max_entry.pack(side="left", padx=5)
        self.rand_max_entry.insert(0, "100")''',
    '''        self.rand_max_entry = ctk.CTkEntry(rand_frame, width=55, placeholder_text="92")
        self.rand_max_entry.pack(side="left", padx=5)
        self.rand_max_entry.insert(0, "92")''')

# ── 5. 时长默认 600~900，并加说明 ──
rep('''        time_mode_row = ctk.CTkFrame(shared_panel, fg_color="transparent")''',
    '''        ctk.CTkLabel(shared_panel,
                     text="课时时长 = 下限，不足部分由平台要求（timelitsec）自动补齐；上限 1500s。",
                     font=ctk.CTkFont(size=10), text_color=("#64748b", "#7c8db5")
                     ).pack(anchor="w", pady=(0, 6))

        time_mode_row = ctk.CTkFrame(shared_panel, fg_color="transparent")''')
rep('''        self.fixed_time_entry = ctk.CTkEntry(time_mode_row, width=65, placeholder_text="30")
        self.fixed_time_entry.pack(side="left", padx=5)
        self.fixed_time_entry.insert(0, "30")''',
    '''        self.fixed_time_entry = ctk.CTkEntry(time_mode_row, width=65, placeholder_text="720")
        self.fixed_time_entry.pack(side="left", padx=5)
        self.fixed_time_entry.insert(0, "720")''')
rep('''        self.time_min_entry = ctk.CTkEntry(rand_time_row, width=55, placeholder_text="60")
        self.time_min_entry.pack(side="left", padx=5)
        self.time_min_entry.insert(0, "60")''',
    '''        self.time_min_entry = ctk.CTkEntry(rand_time_row, width=55, placeholder_text="600")
        self.time_min_entry.pack(side="left", padx=5)
        self.time_min_entry.insert(0, "600")''')
rep('''        self.time_max_entry = ctk.CTkEntry(rand_time_row, width=55, placeholder_text="120")
        self.time_max_entry.pack(side="left", padx=5)
        self.time_max_entry.insert(0, "120")''',
    '''        self.time_max_entry = ctk.CTkEntry(rand_time_row, width=55, placeholder_text="900")
        self.time_max_entry.pack(side="left", padx=5)
        self.time_max_entry.insert(0, "900")''')

# ── 6. 线程输入：固定 1 ──
rep('''        ctk.CTkLabel(thread_row, text="最大线程数:").pack(side="left")
        self.threads_entry = ctk.CTkEntry(thread_row, width=65, placeholder_text="10")
        self.threads_entry.pack(side="left", padx=5)
        self.threads_entry.insert(0, "10")''',
    '''        ctk.CTkLabel(thread_row, text="并发数:").pack(side="left")
        self.threads_entry = ctk.CTkEntry(thread_row, width=65, placeholder_text="1")
        self.threads_entry.pack(side="left", padx=5)
        self.threads_entry.insert(0, "1")
        ctk.CTkLabel(thread_row, text="（同账号只能 1，多个会因学习票据互踢而丢失时长）",
                     font=ctk.CTkFont(size=10), text_color=("#64748b", "#7c8db5")).pack(side="left")''')

# ── 7. 预设逻辑 ──
rep('''    def _on_task_mode_change(self):''',
    '''    PRESETS = {
        "安全（推荐）": dict(rate=(80, 92), dur=(600, 900), cooldown_every=4,
                         cooldown=(400, 900), cap=24,
                         note="每节课按平台要求学满，每 4 节休息 7~15 分钟，单日最多 24 节。"),
        "标准": dict(rate=(75, 90), dur=(480, 720), cooldown_every=6,
                   cooldown=(120, 300), cap=36,
                   note="节奏略快，风险仍可控；适合课时较少、时间紧的情况。"),
        "极速": dict(rate=(70, 85), dur=(120, 300), cooldown_every=0,
                   cooldown=(0, 0), cap=999,
                   note="⚠ 明显快于平台要求时长，被时钟流速校验/隔天复核打回的概率很高，仅应急用。"),
    }

    def _on_preset_change(self, choice):
        p = self.PRESETS.get(choice)
        if not p:
            return
        self.risk_preset = {"安全（推荐）": "safe", "标准": "standard", "极速": "fast"}[choice]
        self.daily_lesson_cap = p["cap"]
        self.cooldown_every = p["cooldown_every"]
        self.cooldown_range = p["cooldown"]

        # 同步控件
        lo, hi = p["rate"]
        self.rate_var.set("random")
        self.rand_min_entry.delete(0, "end")
        self.rand_min_entry.insert(0, str(lo))
        self.rand_max_entry.delete(0, "end")
        self.rand_max_entry.insert(0, str(hi))
        self._on_rate_mode_change()

        dlo, dhi = p["dur"]
        self.time_var.set("random")
        self.time_min_entry.delete(0, "end")
        self.time_min_entry.insert(0, str(dlo))
        self.time_max_entry.delete(0, "end")
        self.time_max_entry.insert(0, str(dhi))
        self._on_time_mode_change()

        self.threads_entry.delete(0, "end")
        self.threads_entry.insert(0, "1")

        self.preset_label.configure(text=f"当前：{choice}")
        self._update_estimate()

    def _update_estimate(self):
        try:
            lo = int(self.time_min_entry.get())
            hi = int(self.time_max_entry.get())
        except (ValueError, AttributeError):
            lo, hi = 600, 900
        avg = max(1, (lo + hi) // 2)
        cap = min(self.daily_lesson_cap, 999)
        per_day_min = avg * cap / 60.0
        extra = ""
        if self.cooldown_every:
            extra = f"，另加每 {self.cooldown_every} 节约 {self.cooldown_range[0]//60}~" \\
                    f"{self.cooldown_range[1]//60} 分钟休息"
        self.estimate_label.configure(
            text=f"⏱ 单节约 {lo//60}~{hi//60} 分钟；单日上限 {cap} 节 ≈ {per_day_min/60:.1f} 小时{extra}。"
                 f"课时多时请分几天跑，别一次刷完。")

    def _on_task_mode_change(self):''')

# ── 9. 启动前校验 ──
rep('''        try:
            # 时长参数（两种模式共用）
            if self.time_var.get() == "fixed":
                duration_val = int(self.fixed_time_entry.get())''',
    '''        try:
            # 并发：同账号票据互斥，强制 1
            try:
                want_threads = int(self.threads_entry.get())
            except (ValueError, AttributeError):
                want_threads = 1
            if want_threads != 1:
                self.threads_entry.delete(0, "end")
                self.threads_entry.insert(0, "1")
                self._log("[!] 并发已强制改为 1：同账号多个课时会互相顶掉学习票据，反而丢时长", "log_warning")

            # 时长参数（两种模式共用）
            if self.time_var.get() == "fixed":
                duration_val = int(self.fixed_time_entry.get())''')

rep('''            # 线程数（共用）
            max_threads = int(self.threads_entry.get())''',
    '''            # 时长范围校验
            for v in ([duration_val] if self.time_var.get() == "fixed" else [lo, hi]):
                if v < 30:
                    self._log("[!] 单课时时长至少 30 秒（更短必被平台判为异常）", "log_error")
                    return
                if v > 1500:
                    self._log("[!] 单课时时长最多 1500 秒（平台单页上限 30 分钟）", "log_error")
                    return

            # 线程数（共用）
            max_threads = 1''')

# ── 10. 正确率范围校验 ──
rep('''                if self.rate_var.get() == "fixed":
                    self.curriculum_rate = int(self.fixed_rate_entry.get())
                    self.curriculum_random = False''',
    '''                if self.rate_var.get() == "fixed":
                    r = int(self.fixed_rate_entry.get())
                    if not 50 <= r <= 100:
                        self._log("[!] 正确率需在 50~100 之间", "log_error")
                        return
                    self.curriculum_rate = r
                    self.curriculum_random = False''')

# ── 11. 启动确认（预计耗时）──
rep('''        self._log("─" * 55)
        self.stop_requested = False''',
    '''        # 启动前确认：把"要跑多久"讲清楚
        try:
            if self.time_var.get() == "fixed":
                avg_dur = int(self.fixed_time_entry.get())
            else:
                avg_dur = (int(self.time_min_entry.get()) + int(self.time_max_entry.get())) // 2
        except ValueError:
            avg_dur = 720
        cap = self.daily_lesson_cap
        est_h = avg_dur * cap / 3600.0
        msg = (f"本次最多处理 {cap} 个课时（单日上限）\\n"
               f"单课时按约 {avg_dur // 60} 分钟计算，满负荷约需 {est_h:.1f} 小时。\\n\\n"
               f"运行期间请保持窗口打开，可以最小化。\\n"
               f"如果课时很多，建议分几天完成——一次性刷完更容易被平台隔天复核清掉。\\n\\n"
               f"现在开始吗？")
        if not messagebox.askyesno("确认开始", msg):
            return

        self._log("─" * 55)
        self.stop_requested = False''')

# ── 12. task_finished 终态兜底 ──
rep('''        elif t == "time_complete":''',
    '''        elif t == "task_finished":
            # 无论成功/异常，线程都发这个，保证控件不会永久灰掉
            if self.running:
                self._set_running(False, "就绪")
        elif t == "time_complete":''')

# ── 13. 刷新课程失败也要恢复控件 ──
rep('''        elif t == "login_fail":''',
    '''        elif t == "refresh_fail":
            self._log(f"刷新失败: {msg.get('error', '')}", "log_error")
            self._set_running(False, "就绪")
        elif t == "login_fail":''')

open(P, "w", encoding="utf-8").write(src)
print("patch5 ok")
