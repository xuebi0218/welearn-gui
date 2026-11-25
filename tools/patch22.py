# -*- coding: utf-8 -*-
"""v4.0 补丁 22：进度区重做——总览卡片 + 每路一条真进度条 + 卡住检测。"""
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


# ── 1. 用卡片替换原来的「一条进度条 + 一个文本框」──
old_block_start = '''        # 进度条 + 统计
        progress_frame = ctk.CTkFrame(self.task_frame, fg_color="transparent")'''
old_block_end = '''        # 单节上限'''
i0 = src.index(old_block_start)
i1 = src.index(old_block_end)

new_block = '''        # ── 运行状态卡片 ──
        progress_frame = ctk.CTkFrame(self.task_frame, corner_radius=12,
                                      fg_color=("#ffffff", "#0d1626"),
                                      border_width=1, border_color=("#e2e8f0", "#1b2740"))
        progress_frame.pack(fill="x", padx=15, pady=(10, 10))

        head = ctk.CTkFrame(progress_frame, fg_color="transparent")
        head.pack(fill="x", padx=14, pady=(12, 0))
        ctk.CTkLabel(head, text="运行状态", font=ctk.CTkFont(size=13, weight="bold")
                     ).pack(side="left")
        self.prog_badge = ctk.CTkLabel(head, text="空闲", font=ctk.CTkFont(size=11),
                                       text_color=("#64748b", "#8aa0c0"),
                                       fg_color=("#f1f5f9", "#16233a"), corner_radius=9,
                                       padx=9, pady=2)
        self.prog_badge.pack(side="right")

        # 总进度：大百分比 + ETA
        total_row = ctk.CTkFrame(progress_frame, fg_color="transparent")
        total_row.pack(fill="x", padx=14, pady=(8, 0))
        self.prog_pct = ctk.CTkLabel(total_row, text="0%", font=ctk.CTkFont(size=26, weight="bold"),
                                     text_color=("#1b2a4a", "#e9f1ff"))
        self.prog_pct.pack(side="left")
        self.task_progress_label = ctk.CTkLabel(total_row, text="尚未开始",
                                                font=ctk.CTkFont(size=11),
                                                text_color=("#64748b", "#8aa0c0"))
        self.task_progress_label.pack(side="left", padx=(10, 0), pady=(8, 0))
        self.eta_label = ctk.CTkLabel(total_row, text="", font=ctk.CTkFont(size=11),
                                      text_color=("#64748b", "#8aa0c0"))
        self.eta_label.pack(side="right", pady=(8, 0))

        self.task_progress_bar = ctk.CTkProgressBar(progress_frame, height=10, corner_radius=5,
                                                    progress_color=("#4cc9d6", "#5b8def"))
        self.task_progress_bar.pack(fill="x", padx=14, pady=(4, 8))
        self.task_progress_bar.set(0)

        # 三格统计
        stat_row = ctk.CTkFrame(progress_frame, fg_color="transparent")
        stat_row.pack(fill="x", padx=14, pady=(0, 10))
        self.stat_labels = {}
        for key, title in (("done", "已完成"), ("running", "进行中"), ("waiting", "待处理")):
            cell = ctk.CTkFrame(stat_row, corner_radius=9, fg_color=("#f6f9fc", "#111d31"))
            cell.pack(side="left", fill="x", expand=True, padx=(0, 6))
            ctk.CTkLabel(cell, text=title, font=ctk.CTkFont(size=10),
                         text_color=("#7b8aa5", "#7f93b3")).pack(pady=(6, 0))
            v = ctk.CTkLabel(cell, text="0", font=ctk.CTkFont(size=16, weight="bold"),
                             text_color=("#1b2a4a", "#e9f1ff"))
            v.pack(pady=(0, 6))
            self.stat_labels[key] = v

        # 每路一行（真进度条，最多 8 行）
        self.lane_area = ctk.CTkFrame(progress_frame, fg_color="transparent")
        self.lane_area.pack(fill="x", padx=14, pady=(0, 4))
        self.lane_rows = {}
        self.lane_empty = ctk.CTkLabel(self.lane_area, text="开始后这里会显示每一路的学习进度",
                                       font=ctk.CTkFont(size=11),
                                       text_color=("#94a3b8", "#5f7396"))
        self.lane_empty.pack(anchor="w", pady=(2, 6))

        self.stall_label = ctk.CTkLabel(progress_frame, text="", font=ctk.CTkFont(size=11),
                                        text_color=("#b45309", "#e0b070"))
        self.stall_label.pack(anchor="w", padx=14, pady=(0, 10))

        self.task_stats_label = ctk.CTkLabel(progress_frame, text="", font=ctk.CTkFont(size=10),
                                             text_color=("#94a3b8", "#5f7396"))
        self.task_stats_label.pack(anchor="w", padx=14, pady=(0, 10))
        self._lane_state = {}
        self._task_total = 0
        self._task_done = 0

'''
src = src[:i0] + new_block + src[i1:]

# ── 2. 重写 _render_lanes：真控件 ──
old_render_start = '''    def _render_lanes(self):
        if not hasattr(self, "lane_box"):
            return'''
i2 = src.index(old_render_start)
i3 = src.index('''    def _tick_mascot(self):''')

new_render = '''    def _ensure_lane_row(self, lane_id):
        """按需创建一路的进度行。"""
        if lane_id in self.lane_rows:
            return self.lane_rows[lane_id]
        if self.lane_empty.winfo_ismapped():
            self.lane_empty.pack_forget()
        row = ctk.CTkFrame(self.lane_area, fg_color="transparent", height=26)
        row.pack(fill="x", pady=1)
        row.pack_propagate(False)
        dot = ctk.CTkLabel(row, text="●", width=14, font=ctk.CTkFont(size=11),
                           text_color=("#94a3b8", "#64748b"))
        dot.pack(side="left")
        name = ctk.CTkLabel(row, text=f"L{lane_id + 1}", width=150, anchor="w",
                            font=ctk.CTkFont(size=11))
        name.pack(side="left", padx=(2, 6))
        bar = ctk.CTkProgressBar(row, width=150, height=6, corner_radius=3,
                                 progress_color=("#4cc9d6", "#5b8def"))
        bar.pack(side="left")
        bar.set(0)
        pct = ctk.CTkLabel(row, text="0%", width=38, font=ctk.CTkFont(size=10),
                           text_color=("#64748b", "#8aa0c0"))
        pct.pack(side="left", padx=(6, 0))
        info = ctk.CTkLabel(row, text="", anchor="w", font=ctk.CTkFont(size=10),
                            text_color=("#94a3b8", "#5f7396"))
        info.pack(side="left", padx=(6, 0))
        self.lane_rows[lane_id] = {"dot": dot, "name": name, "bar": bar, "pct": pct, "info": info}
        return self.lane_rows[lane_id]

    def _render_lanes(self):
        """把 _lane_state 画成每路一行：状态点 + 节名 + 进度条 + 已学/目标 + 剩余。"""
        if not hasattr(self, "lane_rows"):
            return
        now = time.time()
        running = getattr(self, "running", False)
        stalled = []
        for lane_id in sorted(self._lane_state.keys()):
            st = self._lane_state[lane_id]
            w = self._ensure_lane_row(lane_id)
            loc = (st.get("loc") or "?")
            loc_short = loc if len(loc) <= 24 else loc[:23] + "…"
            el = int(st.get("elapsed") or 0)
            tg = max(1, int(st.get("target") or 1))
            pct = min(100, int(el * 100 / tg))
            w["name"].configure(text=f"L{lane_id + 1}  {loc_short}")
            w["bar"].set(pct / 100.0)
            w["pct"].configure(text=f"{pct}%")
            if st.get("done"):
                w["dot"].configure(text_color=("#16a34a", "#4ade80"))
                w["info"].configure(text="已完成")
                continue
            idle = now - float(st.get("ts") or now)
            eta = max(0, tg - el)
            if running and idle > 90:
                w["dot"].configure(text_color=("#d97706", "#fbbf24"))
                w["info"].configure(text=f"等待中 · {int(idle)}s 无变化")
                stalled.append(f"L{lane_id + 1}")
            else:
                w["dot"].configure(text_color=("#4cc9d6", "#5b8def"))
                w["info"].configure(
                    text=f"{el // 60:02d}:{el % 60:02d}/{tg // 60:02d}:{tg % 60:02d} · 剩{eta // 60}分")

        if stalled:
            self.stall_label.configure(
                text=f"⚠ {'、'.join(stalled)} 超过 90 秒没有进展——多数是在等平台返回，"
                     f"若持续 3 分钟不动可停止重试")
        else:
            self.stall_label.configure(text="")

        n_lane = len(self._lane_state)
        self.stat_labels["running"].configure(text=str(sum(
            1 for v in self._lane_state.values() if not v.get("done"))))
        if n_lane == 0 and not self.lane_empty.winfo_ismapped():
            self.lane_empty.pack(anchor="w", pady=(2, 6))

    def _tick_progress(self):
        """每 2 秒刷新一次状态点与停留时长（只在运行时有意义）。"""
        try:
            if getattr(self, "running", False):
                self._render_lanes()
                self.root.after(2000, self._tick_progress)
        except Exception:
            pass

'''
src = src[:i2] + new_render + src[i3:]

open(P, "w", encoding="utf-8").write(src)
print("patch22 ok")
