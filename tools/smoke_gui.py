# -*- coding: utf-8 -*-
"""GUI 冒烟测试：构建界面 → 切换预设 → 模拟消息 → 退出。"""
import sys

sys.path.insert(0, "src")
import welearn_gui as wg   # noqa: E402

wg.WelearnApp._show_disclaimer = lambda self: None   # 跳过模态免责声明

app = wg.WelearnApp()
root = app.root
root.update()

print("mascot loaded:", bool(getattr(app, "_mascot_img", None)))
print("defaults: rate=%s dur=%s threads=%s preset=%s cap=%s" % (
    app.curriculum_rate, app.curriculum_duration,
    app.curriculum_max_threads, app.risk_preset, app.daily_lesson_cap))
print("estimate:", app.estimate_label.cget("text")[:80])

app._on_preset_change("标准")
root.update()
print("after 标准: dur=%s cap=%s estimate=%s" % (
    app.curriculum_duration, app.daily_lesson_cap,
    app.estimate_label.cget("text")[:60]))

app._on_preset_change("安全（推荐）")
root.update()

# 模拟后台消息：进度 + 终态
app._handle_message({"type": "progress", "current": 3, "total": 10})
app._handle_message({"type": "task_finished"})
root.update()
print("running flag:", app.running)

# 页面切换
for p in ("help", "settings", "donate", "home"):
    app._show_page(p)
    root.update()

root.after(200, root.destroy)
root.mainloop()
print("smoke ok")
