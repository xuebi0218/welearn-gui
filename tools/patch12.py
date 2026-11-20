# -*- coding: utf-8 -*-
"""v3.6 补丁 12：未学满不谎报「已完成」（严格模式）。"""
import sys

P = "src/welearn_gui.py"
src = open(P, encoding="utf-8").read()


def rep(old, new, cnt=1):
    global src
    n = src.count(old)
    if n != cnt:
        print("MISMATCH(%d):" % n, old[:80].replace("\n", "\\n"))
        sys.exit(1)
    src = src.replace(old, new)


# 计算是否学满
rep('''    # ── 3. 提交 SCORM 数据 ──
    now_utc = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())''',
    '''    # ── 3. 提交 SCORM 数据 ──
    # 严格模式：时长没学满就不谎报 completed。
    # 平台风控看的是「完成得比要求快多少」，秒完成的 completed 是典型脚本特征。
    learned_total = base_total + int(elapsed)
    if timer_target:
        reached_final = learned_total >= timer_target * 0.95
        progress_val = min(1.0, learned_total / float(timer_target))
    else:
        reached_final = target == 0 or elapsed >= target * 0.95
        progress_val = 1.0 if reached_final else 0.5
    result["reached"] = reached_final

    cstatus_val = "completed" if reached_final else "incomplete"
    progress_str = f"{progress_val:.2f}"
    now_utc = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())''')

rep('''            "completion_status": "completed",''',
    '''            "completion_status": cstatus_val,''')
rep('''            "progress_measure": "1",''',
    '''            "progress_measure": progress_str,''')
rep('''            "session_time": str(int(elapsed)),
            "success_status": "unknown",
            "total_time": str(base_total + int(elapsed)),''',
    '''            "session_time": str(int(elapsed)),
            "success_status": "unknown",
            "total_time": str(learned_total),''')

# savescoinfo 也按实际进度
rep('''    resp2 = session.post(AJAX_SCO_URL,
                         data={"action": "savescoinfo160928", "cid": cid, "scoid": scoid,
                               "uid": uid, "progress": "100", "crate": str(crate_int),
                               "status": "unknown", "cstatus": "completed", "trycount": "0",
                               "session_time": str(int(elapsed)),
                               "total_time": str(base_total + int(elapsed)),
                               "endcaltime": "true", "nocache": random.random()},''',
    '''    resp2 = session.post(AJAX_SCO_URL,
                         data={"action": "savescoinfo160928", "cid": cid, "scoid": scoid,
                               "uid": uid,
                               "progress": str(int(round(progress_val * 100))),
                               "crate": str(crate_int),
                               "status": "unknown", "cstatus": cstatus_val, "trycount": "0",
                               "session_time": str(int(elapsed)),
                               "total_time": str(learned_total),
                               "endcaltime": "true" if reached_final else "false",
                               "nocache": random.random()},''')

# 返回值里补 reached
rep('''    result = {"way1": False, "way2": False, "questions": 0, "target": int(learntime or 0),
              "timelitsec": 0, "verified": None, "stopped": False, "note": ""}''',
    '''    result = {"way1": False, "way2": False, "questions": 0, "target": int(learntime or 0),
              "timelitsec": 0, "verified": None, "stopped": False, "note": "",
              "reached": False}''')

open(P, "w", encoding="utf-8").write(src)
print("patch12 ok")
