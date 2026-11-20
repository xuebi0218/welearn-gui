# -*- coding: utf-8 -*-
"""v3.6 补丁 9：日志工具条、进度 ETA、偏好持久化、快捷键。"""
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


# 1) 日志头加「清空 / 导出」按钮
rep('''        ctk.CTkLabel(log_header, text="📋 运行日志",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=("#8b949e", "#8b949e")).pack(anchor="w")''',
    '''        title_row = ctk.CTkFrame(log_header, fg_color="transparent")
        title_row.pack(fill="x")
        ctk.CTkLabel(title_row, text="📋 运行日志",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=("#8b949e", "#8b949e")).pack(side="left")
        ctk.CTkButton(title_row, text="清空", width=44, height=20, corner_radius=6,
                      fg_color="transparent", hover_color=("#30363d", "#21262d"),
                      text_color=("#64748b", "#8b949e"),
                      font=ctk.CTkFont(size=10),
                      command=self._clear_log).pack(side="right", padx=(4, 0))
        ctk.CTkButton(title_row, text="导出", width=44, height=20, corner_radius=6,
                      fg_color="transparent", hover_color=("#30363d", "#21262d"),
                      text_color=("#64748b", "#8b949e"),
                      font=ctk.CTkFont(size=10),
                      command=self._export_log).pack(side="right")''')

# 2) 日志工具方法
rep('''    def _set_running(self, running, status_text):''',
    '''    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _export_log(self):
        from tkinter import filedialog
        try:
            content = self.log_text.get("1.0", "end-1c")
        except Exception:
            return
        if not content.strip():
            self._log("日志为空，没什么可导出的", "log_warning")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt", filetypes=[("文本文件", "*.txt")],
            initialfile=time.strftime("welearn-log-%Y%m%d-%H%M.txt"))
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            self._log(f"日志已导出：{path}", "log_success")
        except Exception as e:
            self._log(f"导出失败：{e}", "log_error")

    def _set_running(self, running, status_text):''')

# 3) 进度显示预计剩余时间
rep('''            elif ratio > 0:
                self.task_progress_label.configure(text=f"⏳ 进度: {current}/{total} | 剩余 {remaining} 个 | 请耐心等待...", text_color="#38bdf8")''',
    '''            elif ratio > 0:
                avg = getattr(self, "_avg_lesson_sec", 720)
                eta_min = int(remaining * avg / 60)
                eta = f"{eta_min} 分钟" if eta_min < 90 else f"{eta_min/60:.1f} 小时"
                self.task_progress_label.configure(
                    text=f"⏳ 进度: {current}/{total} | 剩余 {remaining} 个 | 预计还需约 {eta}",
                    text_color="#38bdf8")''')

# 4) 启动时记住平均课时耗时，供 ETA 用
rep('''        self._log("─" * 55)
        self.stop_requested = False''',
    '''        try:
            if self.time_var.get() == "fixed":
                self._avg_lesson_sec = int(self.fixed_time_entry.get())
            else:
                self._avg_lesson_sec = (int(self.time_min_entry.get()) + int(self.time_max_entry.get())) // 2
        except ValueError:
            self._avg_lesson_sec = 720

        self._log("─" * 55)
        self.stop_requested = False''')

# 5) 偏好持久化（预设/语言/主题之外，再记节奏参数）
rep('''    def _save_prefs(self):
        """保存当前偏好到配置文件"""
        self._config["lang"] = self.lang
        self._config["appearance"] = ctk.get_appearance_mode()
        _save_config(self._config)''',
    '''    def _save_prefs(self):
        """保存当前偏好到配置文件"""
        self._config["lang"] = self.lang
        self._config["appearance"] = ctk.get_appearance_mode()
        try:
            self._config["preset"] = self.risk_preset
            self._config["daily_cap"] = self.daily_lesson_cap
            self._config["rate"] = list(self.curriculum_rate) if isinstance(self.curriculum_rate, list) \\
                else self.curriculum_rate
            self._config["ratio_random"] = self.curriculum_random
        except Exception:
            pass
        _save_config(self._config)''')

# 6) 启动时恢复上次预设
rep('''        # 初始化节奏预估文案
        try:
            self._update_estimate()''',
    '''        # 恢复上次使用的节奏预设
        saved_preset = (self._config or {}).get("preset")
        preset_name = {"safe": "安全（推荐）", "standard": "标准", "fast": "极速"}.get(saved_preset)
        if preset_name:
            try:
                self.preset_seg.set(preset_name)
                self._on_preset_change(preset_name)
            except Exception:
                pass

        # 初始化节奏预估文案
        try:
            self._update_estimate()''')

# 7) 快捷键：Ctrl+Enter 开始，Esc 停止
rep('''        self.root.protocol("WM_DELETE_WINDOW", self._on_close)''',
    '''        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Control-Return>", lambda _e: self._on_start_task())
        self.root.bind("<Escape>", lambda _e: self._on_stop() if self.running else None)''')

open(P, "w", encoding="utf-8").write(src)
print("patch9 ok")
