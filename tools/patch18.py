# -*- coding: utf-8 -*-
"""v3.9 补丁 18：实时进度（每路状态）+ 单节上限 + 停止统计修正。"""
import sys

P = "src/welearn_gui.py"
src = open(P, encoding="utf-8").read()


def rep(old, new, cnt=1):
    global src
    n = src.count(old)
    if n != cnt:
        print("MISMATCH(%d):" % n, old[:100].replace("\n", "\\n"))
        sys.exit(1)
    src = src.replace(old, new)


# ── 1. process_one：节内进度回调 + 停止也统计 + 单节上限 ──
rep('''            r = welearn_curriculum_submit(session, cid, uid, classid, scoid, crate,
                                          learntime=dur, stop_check=lambda: app.stop_requested,
                                          unitidx=unit_i)
            if r["stopped"]:
                app.message_queue.put({"type": "log_warning",
                                       "text": f'  ⏹ {loc} 已停止（已学 {r["target"]}s 已落库）'})
                return''',
    '''            def _cb(info, _loc=loc, _lane=lane_id):
                app.message_queue.put({"type": "lesson_progress", "lane": _lane,
                                       "loc": _loc, "elapsed": info["elapsed"],
                                       "target": info["target"], "timelitsec": info["timelitsec"]})

            r = welearn_curriculum_submit(session, cid, uid, classid, scoid, crate,
                                          learntime=dur, stop_check=lambda: app.stop_requested,
                                          unitidx=unit_i,
                                          lesson_cap=int(getattr(app, "lesson_cap", 0) or 0),
                                          progress_cb=_cb)
            app.message_queue.put({"type": "lane_done", "lane": lane_id})
            if r["stopped"]:
                with stats_lock:
                    counters["way1_ok" if r["way1"] else "way1_fail"] += 1
                    counters["way2_ok" if r["way2"] else "way2_fail"] += 1
                    counters["stopped"] = counters.get("stopped", 0) + 1
                app.message_queue.put({"type": "log_warning",
                                       "text": f'  ⏹ {loc} 已停止（本次 {r["elapsed"]}s，'
                                               f'回读 {r["verified"] if r["verified"] is not None else "?"}s）'})
                return''')

# ── 2. 开始前的说明：写清「本节要多久」 ──
rep('''    app.message_queue.put({"type": "log",
                           "text": "ℹ️ 每个小节的时长按平台要求（timelitsec）自动补齐，实际耗时取决于课件要求。"})''',
    '''    _cap = int(getattr(app, "lesson_cap", 0) or 0)
    cap_txt = (f"单节最多 {_cap // 60} 分钟" if _cap else "单节不设上限")
    app.message_queue.put({"type": "log",
                           "text": f"ℹ️ 每节先查平台要求（多数 1800s＝30 分钟），按缺口补齐；{cap_txt}。"})
    app.message_queue.put({"type": "log",
                           "text": "ℹ️ 运行中每一路都会实时显示「已学/目标」，长时间没变化才说明卡住。"})''')

# ── 3. GUI：每路状态面板 ──
rep('''        self.task_stats_label = ctk.CTkLabel(progress_frame, text="", font=ctk.CTkFont(size=11),
                                              text_color=("#64748b", "#94a3b8"))
        self.task_stats_label.pack(anchor="w")''',
    '''        self.task_stats_label = ctk.CTkLabel(progress_frame, text="", font=ctk.CTkFont(size=11),
                                              text_color=("#64748b", "#94a3b8"))
        self.task_stats_label.pack(anchor="w")

        # 每路实时状态（最多 8 行）
        self.lane_box = ctk.CTkTextbox(progress_frame, height=88, font=ctk.CTkFont(size=11),
                                       fg_color=("#f8fafc", "#0b1220"),
                                       text_color=("#334155", "#c9d6ea"),
                                       border_width=1, border_color=("#e2e8f0", "#1b2740"))
        self.lane_box.pack(fill="x", pady=(6, 0))
        self.lane_box.configure(state="disabled")
        self._lane_state = {}

        # 单节上限
        cap_row = ctk.CTkFrame(progress_frame, fg_color="transparent")
        cap_row.pack(fill="x", pady=(6, 0))
        ctk.CTkLabel(cap_row, text="单节上限:", font=ctk.CTkFont(size=11)).pack(side="left")
        self.cap_menu = ctk.CTkOptionMenu(cap_row, values=["10 分钟", "15 分钟", "20 分钟", "30 分钟", "不设上限"],
                                          width=110, height=26, font=ctk.CTkFont(size=11),
                                          command=self._on_cap_change)
        self.cap_menu.pack(side="left", padx=6)
        _cap = int(getattr(self, "lesson_cap", 1200) or 0)
        self.cap_menu.set(f"{_cap // 60} 分钟" if _cap else "不设上限")
        ctk.CTkLabel(cap_row, text="（平台要求 30 分钟时，超限就下次再补，更像真人）",
                     font=ctk.CTkFont(size=10), text_color=("#64748b", "#7c8db5")).pack(side="left")''')

# ── 4. 回调方法 ──
rep('''    def _tick_mascot(self):''',
    '''    def _on_cap_change(self, choice):
        self.lesson_cap = 0 if choice == "不设上限" else int(choice.split()[0]) * 60
        self._save_prefs()

    def _render_lanes(self):
        if not hasattr(self, "lane_box"):
            return
        lines = []
        for i in range(8):
            st = self._lane_state.get(i)
            if not st:
                continue
            el, tg = st["elapsed"], max(1, st["target"])
            pct = min(100, int(el * 100 / tg))
            bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            eta = max(0, tg - el)
            lines.append(f"L{i + 1} {st['loc'][:38]:<38} {bar} {pct:3d}%  "
                         f"{el // 60:02d}:{el % 60:02d}/{tg // 60:02d}:{tg % 60:02d}  剩{eta // 60}分")
        if not lines:
            lines = ["（未开始）"]
        self.lane_box.configure(state="normal")
        self.lane_box.delete("1.0", "end")
        self.lane_box.insert("1.0", "\\n".join(lines))
        self.lane_box.configure(state="disabled")

    def _tick_mascot(self):''')

open(P, "w", encoding="utf-8").write(src)
print("patch18 ok")
