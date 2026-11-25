# -*- coding: utf-8 -*-
"""v4.0 补丁 23：五态判定 + 每路入账统计 + 运行结果卡。"""
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


# ── 1. worker：lane_done 带回合数据 ──
rep('''            app.message_queue.put({"type": "lane_done", "lane": lane_id})
            if r["stopped"]:''',
    '''            app.message_queue.put({"type": "lane_done", "lane": lane_id, "loc": loc,
                                   "elapsed": r.get("elapsed", 0),
                                   "target": r.get("target", 0),
                                   "verified": r.get("verified"),
                                   "base": r.get("base", 0),
                                   "capped": r.get("capped", False),
                                   "way1": r["way1"], "way2": r["way2"],
                                   "stopped": r["stopped"]})
            if r["stopped"]:''')

# ── 2. 五态判定：等待 / 心跳超时 / 疑似中断 ──
rep('''            idle = now - float(st.get("ts") or now)
            eta = max(0, tg - el)
            if running and idle > 90:
                w["dot"].configure(text_color=("#d97706", "#fbbf24"))
                w["info"].configure(text=f"等待中 · {int(idle)}s 无变化")
                stalled.append(f"L{lane_id + 1}")
            else:
                w["dot"].configure(text_color=("#4cc9d6", "#5b8def"))
                w["info"].configure(
                    text=f"{el // 60:02d}:{el % 60:02d}/{tg // 60:02d}:{tg % 60:02d} · 剩{eta // 60}分")''',
    '''            idle = now - float(st.get("ts") or now)
            eta = max(0, tg - el)
            clock = f"{el // 60:02d}:{el % 60:02d}/{tg // 60:02d}:{tg % 60:02d}"
            if running and idle > 120:
                w["dot"].configure(text="◆", text_color=("#b45309", "#f0a35e"))
                w["info"].configure(text=f"疑似中断 · {int(idle)}s 无心跳")
                stalled.append(f"L{lane_id + 1}")
            elif running and idle > 45:
                w["dot"].configure(text="◆", text_color=("#d97706", "#fbbf24"))
                w["info"].configure(text=f"心跳超时 {int(idle)}s · 可继续等待")
                stalled.append(f"L{lane_id + 1}")
            elif running and idle > 32:
                w["dot"].configure(text="◐", text_color=("#5b8def", "#7fa2f0"))
                w["info"].configure(text=f"{clock} · 等待心跳 {int(35 - idle)}s")
            else:
                w["dot"].configure(text="●", text_color=("#4cc9d6", "#5b8def"))
                w["info"].configure(text=f"{clock} · 剩{eta // 60}分")''')

# ── 3. 停留文案去 emoji ──
rep('''        if stalled:
            self.stall_label.configure(
                text=f"⚠ {'、'.join(stalled)} 超过 90 秒没有进展——多数是在等平台返回，"
                     f"若持续 3 分钟不动可停止重试")''',
    '''        if stalled:
            self.stall_label.configure(
                text=f"{'、'.join(stalled)} 超过 45 秒没有心跳——多半是在等平台返回，"
                     f"超过 2 分钟仍不动可停止后重试该节")''')

# ── 4. 每路节名去掉超长、保留课程位置感 ──
rep('''            self._lane_state[msg["lane"]] = {"loc": msg["loc"], "elapsed": msg["elapsed"],
                                             "target": msg["target"]}''',
    '''            self._lane_state[msg["lane"]] = {"loc": msg["loc"], "elapsed": msg["elapsed"],
                                             "target": msg["target"], "ts": time.time()}''')

# ── 5. lane_done：累计入账并标记该路完成 ──
rep('''        elif t == "lane_done":
            self._lane_state.pop(msg["lane"], None)
            self._render_lanes()''',
    '''        elif t == "lane_done":
            lane = msg["lane"]
            gain = 0
            try:
                if msg.get("verified") is not None and msg.get("base") is not None:
                    gain = max(0, int(msg["verified"]) - int(msg.get("base") or 0))
                else:
                    gain = int(msg.get("elapsed") or 0)
            except Exception:
                gain = 0
            self._earned_sec = getattr(self, "_earned_sec", 0) + gain
            self._done_count = getattr(self, "_done_count", 0) + 1
            if msg.get("way1") and msg.get("way2"):
                self._ok_count = getattr(self, "_ok_count", 0) + 1
            else:
                self._fail_count = getattr(self, "_fail_count", 0) + 1
                self._fail_list = getattr(self, "_fail_list", [])
                if msg.get("loc"):
                    self._fail_list.append(msg["loc"])
            st = self._lane_state.get(lane)
            if st:
                st["done"] = True
                st["ts"] = time.time()
                w = self.lane_rows.get(lane)
                if w:
                    w["dot"].configure(text="●", text_color=("#16a34a", "#4ade80"))
                    w["bar"].set(1.0)
                    w["pct"].configure(text="100%")
                    w["info"].configure(text=f"完成 · 计入 {gain}s")
            self.stat_labels["done"].configure(text=str(self._done_count))''')

# ── 6. 进度消息：同步三格统计与总百分比 ──
rep('''            self.task_progress_bar.set(ratio)
            if ratio >= 1.0:''',
    '''            self.task_progress_bar.set(ratio)
            self.prog_pct.configure(text=f"{int(ratio * 100)}%")
            self.stat_labels["waiting"].configure(text=str(remaining))
            self.stat_labels["done"].configure(text=str(current))
            if ratio >= 1.0:''')

# ── 7. 完成后：结果卡 + 徽标 ──
rep('''        elif t == "curriculum_complete":
            total = msg['way1_ok'] + msg['way1_fail']''',
    '''        elif t == "curriculum_complete":
            self._show_result_card(msg)
            total = msg['way1_ok'] + msg['way1_fail']''')

# ── 8. 结果卡实现 ──
rep('''    def _populate_course_menu(self):''',
    '''    def _show_result_card(self, msg):
        """运行结束后的对账卡片：本次入账多少、成了几节、失败在哪。"""
        try:
            earned = int(getattr(self, "_earned_sec", 0))
            done_n = int(getattr(self, "_done_count", 0))
            ok_n = int(getattr(self, "_ok_count", 0))
            fail_n = int(getattr(self, "_fail_count", 0))
            fails = getattr(self, "_fail_list", [])
            stopped = bool(msg.get("stopped"))

            self.result_card.pack(fill="x", padx=14, pady=(0, 10), before=self.lane_area)
            title = "本次运行已停止" if stopped else "本次运行完成"
            self.result_title.configure(text=title)
            mm, ss = divmod(earned, 60)
            self.result_big.configure(text=f"{mm:02d}:{ss:02d}")
            self.result_sub.configure(
                text=f"{done_n} 节 · 成功 {ok_n} · 失败 {fail_n}"
                     + (f" · 平均 {earned // max(1, done_n)}s/节" if done_n else ""))
            if fails:
                names = "、".join(f[:18] for f in fails[:3])
                more = "" if len(fails) <= 3 else f" 等 {len(fails)} 节"
                self.result_hint.configure(text=f"未完成：{names}{more}｜可单独重跑这几节")
            elif done_n:
                self.result_hint.configure(text="时长已回读校验，日志里可逐节核对")
            else:
                self.result_hint.configure(text="本次没有产生提交")
            self.prog_badge.configure(text="已停止" if stopped else "已完成",
                                      text_color=("#b45309", "#e0b070"))
        except Exception as e:
            try:
                self._log(f"[界面] 结果卡渲染异常: {e}", "log_error")
            except Exception:
                pass

    def _populate_course_menu(self):''')

# ── 9. 结果卡控件（放在状态卡内部，进度条下面） ──
rep('''        # 每路一行（真进度条，最多 8 行）''',
    '''        # 结束后的对账卡（默认隐藏）
        self.result_card = ctk.CTkFrame(progress_frame, corner_radius=10,
                                        fg_color=("#eef6fb", "#0f2434"))
        self.result_title = ctk.CTkLabel(self.result_card, text="本次运行完成",
                                         font=ctk.CTkFont(size=12, weight="bold"),
                                         text_color=("#1b2a4a", "#e9f1ff"))
        self.result_title.pack(anchor="w", padx=12, pady=(10, 0))
        self.result_big = ctk.CTkLabel(self.result_card, text="00:00",
                                       font=ctk.CTkFont(size=30, weight="bold"),
                                       text_color=("#0e7490", "#5bd3e3"))
        self.result_big.pack(anchor="w", padx=12)
        ctk.CTkLabel(self.result_card, text="本次入账时长（按服务端回读）",
                     font=ctk.CTkFont(size=10),
                     text_color=("#64748b", "#7f93b3")).pack(anchor="w", padx=13)
        self.result_sub = ctk.CTkLabel(self.result_card, text="",
                                       font=ctk.CTkFont(size=11),
                                       text_color=("#334155", "#c9d6ea"))
        self.result_sub.pack(anchor="w", padx=12, pady=(6, 0))
        self.result_hint = ctk.CTkLabel(self.result_card, text="",
                                        font=ctk.CTkFont(size=10),
                                        text_color=("#64748b", "#8aa0c0"))
        self.result_hint.pack(anchor="w", padx=12, pady=(2, 10))

        # 每路一行（真进度条，最多 8 行）''')

# ── 10. 运行开始时：重置统计、隐藏结果卡、刷新徽标、启动刷新定时器 ──
rep('''        self.stop_requested = False
        self.lesson_only = (mode == "lessononly")''',
    '''        self.stop_requested = False
        self._earned_sec = 0
        self._done_count = 0
        self._ok_count = 0
        self._fail_count = 0
        self._fail_list = []
        if hasattr(self, "result_card") and self.result_card.winfo_ismapped():
            self.result_card.pack_forget()
        if hasattr(self, "prog_badge"):
            self.prog_badge.configure(text="运行中", text_color=("#0e7490", "#5bd3e3"))
        if hasattr(self, "prog_pct"):
            self.prog_pct.configure(text="0%")
        self.root.after(2000, self._tick_progress)
        self.lesson_only = (mode == "lessononly")''')

open(P, "w", encoding="utf-8").write(src)
print("patch23 ok")
