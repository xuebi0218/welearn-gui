# -*- coding: utf-8 -*-
"""v3.9 补丁 19：把 lesson_cap / 每路进度消息接到界面上。"""
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


# 1. 默认值
rep('''        self.cooldown_range = (400, 900)''',
    '''        self.cooldown_range = (400, 900)
        self.lesson_cap = 1200           # 单节最多学多久（秒），0=不设上限''')

# 2. 持久化
rep('''            self._config["daily_cap"] = self.daily_lesson_cap''',
    '''            self._config["daily_cap"] = self.daily_lesson_cap
            self._config["lesson_cap"] = self.lesson_cap''')

# 3. 消息处理：每路进度
rep('''        elif t == "progress":
            current, total = msg["current"], msg["total"]''',
    '''        elif t == "lesson_progress":
            self._lane_state[msg["lane"]] = {"loc": msg["loc"], "elapsed": msg["elapsed"],
                                             "target": msg["target"]}
            self._render_lanes()
        elif t == "lane_done":
            self._lane_state.pop(msg["lane"], None)
            self._render_lanes()
        elif t == "progress":
            current, total = msg["current"], msg["total"]''')

# 4. 开始任务时清空面板
rep('''        self.stop_requested = False
        self.task_progress_bar.set(0)''',
    '''        self.stop_requested = False
        self.task_progress_bar.set(0)
        if hasattr(self, "_lane_state"):
            self._lane_state.clear()
            self._render_lanes()''')

open(P, "w", encoding="utf-8").write(src)
print("patch19 ok")
