# -*- coding: utf-8 -*-
"""v3.9 补丁 17：协议层加「节内进度回调 + 单节上限 + 实际已学秒数」。"""
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


rep('''def welearn_curriculum_submit(session, cid, uid, classid, scoid, crate, learntime=0,
                              stop_check=None, unitidx=0, adaptive=True,
                              duration_cap=DURATION_CAP):''',
    '''def welearn_curriculum_submit(session, cid, uid, classid, scoid, crate, learntime=0,
                              stop_check=None, unitidx=0, adaptive=True,
                              duration_cap=DURATION_CAP, lesson_cap=0, progress_cb=None):''')

rep('''    result = {"way1": False, "way2": False, "questions": 0, "target": int(learntime or 0),
              "timelitsec": 0, "verified": None, "stopped": False, "note": "",
              "reached": False}''',
    '''    result = {"way1": False, "way2": False, "questions": 0, "target": int(learntime or 0),
              "timelitsec": 0, "verified": None, "stopped": False, "note": "",
              "reached": False, "elapsed": 0, "learned_total": 0, "capped": False}''')

rep('''    target = _clamp(target, 0, duration_cap if duration_cap else DURATION_CAP)
    result["target"] = target''',
    '''    # 单节上限：平台要 30 分钟也不要一口气跑完，超限就分段补（更接近真人节奏）
    if lesson_cap and target > lesson_cap:
        target = int(lesson_cap)
        result["capped"] = True
    target = _clamp(target, 0, duration_cap if duration_cap else DURATION_CAP)
    result["target"] = target''')

# 循环内回调
rep('''        if elapsed >= next_hb or reached:
            welearn_time_heartbeat(session, cid, uid, scoid,
                                   str(int(elapsed)), str(base_total + int(elapsed)),
                                   timelitsec=timer_target,
                                   endcaltime="true" if reached else "false")
            next_hb = elapsed + random.randint(HEARTBEAT_MIN, HEARTBEAT_MAX)''',
    '''        if elapsed >= next_hb or reached:
            welearn_time_heartbeat(session, cid, uid, scoid,
                                   str(int(elapsed)), str(base_total + int(elapsed)),
                                   timelitsec=timer_target,
                                   endcaltime="true" if reached else "false")
            next_hb = elapsed + random.randint(HEARTBEAT_MIN, HEARTBEAT_MAX)
            if progress_cb:
                try:
                    progress_cb({"elapsed": int(elapsed), "target": int(target),
                                 "timelitsec": timer_target, "base": base_total,
                                 "reached": reached})
                except Exception:
                    pass''')

rep('''    result["reached"] = reached_final''',
    '''    result["reached"] = reached_final
    result["elapsed"] = int(elapsed)
    result["learned_total"] = learned_total''')

open(P, "w", encoding="utf-8").write(src)
print("patch17 ok")
