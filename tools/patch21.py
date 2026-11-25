# -*- coding: utf-8 -*-
"""v4.0 补丁 21：新增「只刷课」任务模式。"""
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


# ── 1. 模式单选项：加第三种 ──
rep('''        ctk.CTkRadioButton(mode_row, text="⏱ 仅刷时长（心跳保活，不操作题目）",
                           variable=self.task_mode_var, value="timeonly",
                           command=self._on_task_mode_change).pack(anchor="w", pady=2)''',
    '''        ctk.CTkRadioButton(mode_row, text="🎯 只刷课（只做题+答题记录，不补时长）",
                           variable=self.task_mode_var, value="lessononly",
                           command=self._on_task_mode_change).pack(anchor="w", pady=2)
        ctk.CTkRadioButton(mode_row, text="⏱ 仅刷时长（心跳保活，不操作题目）",
                           variable=self.task_mode_var, value="timeonly",
                           command=self._on_task_mode_change).pack(anchor="w", pady=2)''')

# ── 2. 模式切换：只刷课也要正确率面板 ──
rep('''    def _on_task_mode_change(self):
        """切换任务模式时显示/隐藏正确率面板"""
        if self.task_mode_var.get() == "curriculum":''',
    '''    def _on_task_mode_change(self):
        """切换任务模式时显示/隐藏正确率面板"""
        mode = self.task_mode_var.get()
        if mode in ("curriculum", "lessononly"):''')

# ── 3. 启动时按模式分派 ──
rep('''        self._log("─" * 55)
        self.stop_requested = False
        self.task_progress_bar.set(0)''',
    '''        self._log("─" * 55)
        self.stop_requested = False
        self.lesson_only = (mode == "lessononly")
        if self.lesson_only:
            # 只刷课：不补时长，只给到"平台肯收"的最小在线时间
            self.curriculum_duration = [30, 45]
        self.task_progress_bar.set(0)''')

rep('''        if mode == "curriculum":
            dur = self.curriculum_duration
            dur_str = f"{dur}s" if isinstance(dur, int) else f"{dur[0]}~{dur[1]}s"
            rate = self.curriculum_rate
            rate_str = f"{rate}%" if isinstance(rate, int) else f"{rate[0]}~{rate[1]}%"
            self._log(f"📝 刷课并计时 | 正确率={rate_str} | 时长={dur_str} | 线程={max_threads}", "log_warning")
            self._set_running(True, "刷课进行中...")
            threading.Thread(target=thread_curriculum_execute, args=(self,), daemon=True).start()''',
    '''        if mode in ("curriculum", "lessononly"):
            dur = self.curriculum_duration
            dur_str = f"{dur}s" if isinstance(dur, int) else f"{dur[0]}~{dur[1]}s"
            rate = self.curriculum_rate
            rate_str = f"{rate}%" if isinstance(rate, int) else f"{rate[0]}~{rate[1]}%"
            if self.lesson_only:
                self._log(f"🎯 只刷课 | 正确率={rate_str} | 每题在线 {dur_str} | 线程={max_threads}",
                          "log_warning")
                self._log("   只写答题记录与完成进度，不补平台要求的学时；"
                          "后续要学时请再跑「刷课并计时」补齐", "log_warning")
                self._set_running(True, "只刷课进行中...")
            else:
                self._log(f"📝 刷课并计时 | 正确率={rate_str} | 时长={dur_str} | 线程={max_threads}",
                          "log_warning")
                self._set_running(True, "刷课进行中...")
            threading.Thread(target=thread_curriculum_execute, args=(self,), daemon=True).start()''')

# ── 4. worker：只刷课关闭自适应补齐，并按小上限提交 ──
rep('''            r = welearn_curriculum_submit(session, cid, uid, classid, scoid, crate,
                                          learntime=dur, stop_check=lambda: app.stop_requested,
                                          unitidx=unit_i,
                                          lesson_cap=int(getattr(app, "lesson_cap", 0) or 0),
                                          progress_cb=_cb)''',
    '''            lesson_only = bool(getattr(app, "lesson_only", False))
            r = welearn_curriculum_submit(session, cid, uid, classid, scoid, crate,
                                          learntime=dur, stop_check=lambda: app.stop_requested,
                                          unitidx=unit_i,
                                          adaptive=not lesson_only,
                                          lesson_cap=(45 if lesson_only
                                                      else int(getattr(app, "lesson_cap", 0) or 0)),
                                          progress_cb=_cb)''')

# ── 5. 只刷课时的日志用词 ──
rep('''            app.message_queue.put({"type": "log",
                                   "text": f'{tag_pre}[刷课] {loc} → 正确率 {crate}%，至少学 {dur}s'})''',
    '''            _mode_tag = "只刷课" if getattr(app, "lesson_only", False) else "刷课"
            app.message_queue.put({"type": "log",
                                   "text": f'{tag_pre}[{_mode_tag}] {loc} → 正确率 {crate}%，'
                                           f'至少学 {dur}s'})''')

# ── 6. 停止文案 ──
rep('''        mode = "刷课" if self.task_mode_var.get() == "curriculum" else "刷时长"''',
    '''        _m = self.task_mode_var.get()
        mode = {"curriculum": "刷课", "lessononly": "只刷课", "timeonly": "刷时长"}.get(_m, "任务")''')

open(P, "w", encoding="utf-8").write(src)
print("patch21 ok")
