# -*- coding: utf-8 -*-
"""验证多路调度：把提交函数替换成 3 秒假任务，看 N 路是否真的并行抢队列。"""
import queue
import sys
import threading
import time
import types

sys.path.insert(0, "src")
import welearn_gui as wg   # noqa: E402

# ── 假 app ──
app = types.SimpleNamespace()
app.message_queue = queue.Queue()
app.selected_cid, app.uid, app.classid = "3222", "13178431", "779946"
app.curriculum_rate = [80, 92]
app.curriculum_random = True
app.curriculum_duration = [600, 900]
app.curriculum_max_threads = 4
app.daily_lesson_cap = 12
app.cooldown_every = 0
app.cooldown_range = (0, 0)
app.stop_requested = False
app.session = wg.requests.Session()

FAKE_LESSONS = [(0, {"id": f"m-x-{i}", "location": f"Lesson {i}",
                     "isvisible": "true", "iscomplete": "未完成"}) for i in range(12)]

wg.welearn_get_lessons = lambda *a, **k: []
wg._collect_lessons = lambda _app, only_unfinished=True: (FAKE_LESSONS, None)
wg.welearn_check_gates = lambda *a, **k: (False, "")

running = {"n": 0, "peak": 0}
lock = threading.Lock()


def fake_submit(session, cid, uid, classid, scoid, crate, learntime=0, stop_check=None,
                unitidx=0, adaptive=True, duration_cap=1500):
    with lock:
        running["n"] += 1
        running["peak"] = max(running["peak"], running["n"])
    time.sleep(3)
    with lock:
        running["n"] -= 1
    return {"way1": True, "way2": True, "questions": 0, "target": 600, "timelitsec": 1080,
            "verified": 1080, "stopped": False, "note": "", "reached": True}


wg.welearn_curriculum_submit = fake_submit

t0 = time.time()
wg._curriculum_worker(app)
elapsed = time.time() - t0

msgs = []
while not app.message_queue.empty():
    msgs.append(app.message_queue.get())
prog = [m for m in msgs if m["type"] == "progress"]
done = [m for m in msgs if m["type"] == "curriculum_complete"]

print(f"12 个假任务 × 3s，4 路并行 → 总耗时 {elapsed:.1f}s")
print("峰值并发:", running["peak"])
print("进度消息数:", len(prog), "最后一条:", prog[-1] if prog else None)
print("完成消息:", done)
