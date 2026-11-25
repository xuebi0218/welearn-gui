# -*- coding: utf-8 -*-
"""带假数据启动界面，用于核对运行态 UI（不联网、不发请求）。"""
import sys
import time

sys.path.insert(0, "src")
import welearn_gui as wg   # noqa: E402

app = wg.WelearnApp()
import os
app.root.geometry("1060x980+10+10")
app.root.title(f"Welearn 刷课工具 v4.0 · demo{os.getpid()}")
app.root.after(45000, app.root.destroy)
app.root.update()

# 只留下运行状态卡，方便单独核对视觉
for _ch in list(app.task_frame.winfo_children()):
    if _ch is not getattr(app, "prog_frame", None):
        try:
            _ch.destroy()
        except Exception:
            pass
for _w in ("login_frame", "hero_frame"):
    _o = getattr(app, _w, None)
    if _o is not None:
        try:
            _o.pack_forget()
        except Exception:
            pass

app.task_mode_var.set("lessononly")
app._lane_state = {
    0: {"loc": "05. Task 1", "elapsed": 420, "target": 1200, "ts": time.time() - 8},
    1: {"loc": "06. Task 2", "elapsed": 240, "target": 1200, "ts": time.time() - 55},
    2: {"loc": "08. Exercise II", "elapsed": 1140, "target": 1200, "ts": time.time() - 3},
    3: {"loc": "13. Exercise V", "elapsed": 1180, "target": 1200, "ts": time.time() - 4},
}
app.running = True
app._render_lanes()

app.task_progress_bar.set(0.35)
app.task_progress_bar.set_ticks(17)
app.prog_pct.configure(text="35%")
app.task_progress_label.configure(text="进度 6/17 · 剩余 11 个")
app.eta_label.configure(text="预计还需约 28 分钟")
app._done_count = 6
app._running_n = 4
app._refresh_stat_line()
app.prog_badge.configure(text="运行中", text_color=("#0e7490", "#5bd3e3"))


def _scroll_bottom():
    app._refresh_scrollregion()
    app.home_scroll._parent_canvas.yview_moveto(1.0)


app.root.after(800, _scroll_bottom)
app.root.after(1600, _scroll_bottom)
app.root.mainloop()
