# -*- coding: utf-8 -*-
"""真实链路：4 路 worker 并行提交 4 个课时（每节 60s），验证调度+落库。"""
import queue

import os as _os

WL_USER = _os.environ.get("WELEARN_USER", "")
WL_PASS = _os.environ.get("WELEARN_PASS", "")
import sys
import time
import types

sys.path.insert(0, "src")
import welearn_gui as wg   # noqa: E402

CID, UID, CLASSID = "3222", "13178431", "779946"

sess = wg.requests.Session()
wg.welearn_password_login(sess, WL_USER, WL_PASS)

real = []
for unit_i in range(0, 6):
    for c in (wg.welearn_get_lessons(sess, CID, UID, unit_i, CLASSID) or []):
        if str(c.get("isvisible", "true")).lower() == "false":
            continue
        if "未" not in c.get("iscomplete", ""):
            continue
        real.append((unit_i, c))
    if len(real) >= 4:
        break
real = real[:4]
print("lanes:", [(u, c["id"]) for u, c in real])

before = {c["id"]: wg.welearn_sco_requirements(sess, CID, UID, CLASSID, c["id"])["use_seconds"]
          for _u, c in real}

app = types.SimpleNamespace()
app.message_queue = queue.Queue()
app.selected_cid, app.uid, app.classid = CID, UID, CLASSID
app.curriculum_rate = [85, 88]
app.curriculum_random = True
app.curriculum_duration = [60, 60]
app.curriculum_max_threads = 4
app.daily_lesson_cap = 4
app.cooldown_every = 0
app.cooldown_range = (0, 0)
app.stop_requested = False
app.session = sess

wg._collect_lessons = lambda _app, only_unfinished=True: (real, None)

# 测试用：把自适应上限压到 90s，避免跑满 9 分钟的缺口
_orig_submit = wg.welearn_curriculum_submit


def _fast_submit(*a, **k):
    k['duration_cap'] = 90
    return _orig_submit(*a, **k)


wg.welearn_curriculum_submit = _fast_submit

t0 = time.time()
wg._curriculum_worker(app)
elapsed = time.time() - t0

while not app.message_queue.empty():
    m = app.message_queue.get()
    if m["type"].startswith("log") or m["type"] == "curriculum_complete":
        print(m.get("text") or m)

print(f"\n墙钟 {elapsed:.0f}s")
time.sleep(4)
for _u, c in real:
    after = wg.welearn_sco_requirements(sess, CID, UID, CLASSID, c["id"])["use_seconds"]
    print(f'{c["id"]}: {before[c["id"]]} -> {after} (+{after - before[c["id"]]})')
