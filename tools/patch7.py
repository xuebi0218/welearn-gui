# -*- coding: utf-8 -*-
"""v3.6 补丁 7：以 startsco.useSeconds 为真值校验 + 达标提前停表 + 官方参数名。"""
import re
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


# 1) 校验改用 useSeconds（课时列表的 learntime 有延迟，不可靠）
rep('''def welearn_verify_learntime(session, cid, uid, classid, unitidx, scoid):
    """提交后回读：返回该课时当前的累计学习秒数（失败返回 None）。"""
    try:
        lessons = welearn_get_lessons(session, cid, uid, unitidx, classid) or []
        for c in lessons:
            if str(c.get("id")) == str(scoid):
                return _parse_hms(c.get("learntime"))
    except Exception:
        pass
    return None''',
    '''def welearn_verify_learntime(session, cid, uid, classid, unitidx, scoid):
    """提交后回读服务端真值：返回该课时累计学习秒数（失败返回 None）。

    以 startsco160928 的 useSeconds 为准——课时列表里的 learntime 有明显延迟，
    实测刚提交完仍是旧值，用它判断会误报。
    """
    try:
        req = welearn_sco_requirements(session, cid, uid, classid, scoid)
        if req.get("ok"):
            return req["use_seconds"]
    except Exception:
        pass
    try:
        lessons = welearn_get_lessons(session, cid, uid, unitidx, classid) or []
        for c in lessons:
            if str(c.get("id")) == str(scoid):
                return _parse_hms(c.get("learntime"))
    except Exception:
        pass
    return None''')

# 2) 心跳参数名对齐官方（timelimitsec）
rep("""                                  'timelitsec': timelitsec, 'endcaltime': endcaltime,""",
    """                                  'timelitsec': timelitsec, 'timelimitsec': timelitsec,
                                  'endcaltime': endcaltime,""")

# 3) 等待阶段：达标即停 + 记录真实进度
rep('''    # ── 2. 等时长 + 心跳（真实浏览器每 60s 一次，这里 20~32s 更稳）──
    base_total = req["use_seconds"]
    elapsed = 0.0
    next_hb = random.randint(HEARTBEAT_MIN, HEARTBEAT_MAX)
    while elapsed < target:
        if stop_check and stop_check():
            result["stopped"] = True
            result["note"] = "用户停止"
            return result
        step = min(1.0, target - elapsed)
        time.sleep(step * random.uniform(0.92, 1.08))
        elapsed += step
        if elapsed >= next_hb:
            welearn_time_heartbeat(session, cid, uid, scoid,
                                   str(int(elapsed)), str(base_total + int(elapsed)),
                                   timelitsec=req["timelitsec"])
            next_hb = elapsed + random.randint(HEARTBEAT_MIN, HEARTBEAT_MAX)''',
    '''    # ── 2. 等时长 + 心跳（官方 60s 一次，这里 20~32s 更稳；达标即停表）──
    base_total = req["use_seconds"]
    timer_target = req["timelitsec"] or 0
    elapsed = 0.0
    next_hb = random.randint(HEARTBEAT_MIN, HEARTBEAT_MAX)
    reached = timer_target > 0 and base_total >= timer_target
    while elapsed < target and not reached:
        if stop_check and stop_check():
            result["stopped"] = True
            result["note"] = "用户停止"
            return result
        step = min(1.0, target - elapsed)
        time.sleep(step * random.uniform(0.92, 1.08))
        elapsed += step
        if timer_target and base_total + elapsed >= timer_target:
            reached = True
        if elapsed >= next_hb or reached:
            welearn_time_heartbeat(session, cid, uid, scoid,
                                   str(int(elapsed)), str(base_total + int(elapsed)),
                                   timelitsec=timer_target,
                                   endcaltime="true" if reached else "false")
            next_hb = elapsed + random.randint(HEARTBEAT_MIN, HEARTBEAT_MAX)''')

# 4) 结束时心跳带上 endcaltime
rep('''    # 结束时补一次心跳，把最后一段时长落库
    welearn_time_heartbeat(session, cid, uid, scoid,
                           str(int(elapsed)), str(base_total + int(elapsed)),
                           timelitsec=req["timelitsec"])''',
    '''    # 结束时补一次心跳，把最后一段时长落库
    final_reached = bool(timer_target) and (base_total + elapsed) >= timer_target * 0.99
    welearn_time_heartbeat(session, cid, uid, scoid,
                           str(int(elapsed)), str(base_total + int(elapsed)),
                           timelitsec=timer_target,
                           endcaltime="true" if final_reached else "false")''')

# 5) 回读加一次稍后重试（服务端入账有几秒延迟）
rep('''    # ── 4. 回读校验：平台是否真的把时长记上了 ──
    result["verified"] = welearn_verify_learntime(session, cid, uid, classid, unitidx, scoid)
    return result''',
    '''    # ── 4. 回读校验：平台是否真的把时长记上了（入账有几秒延迟，补一次）──
    result["verified"] = welearn_verify_learntime(session, cid, uid, classid, unitidx, scoid)
    if timer_target and (result["verified"] or 0) < min(timer_target, base_total + int(elapsed)):
        time.sleep(3)
        again = welearn_verify_learntime(session, cid, uid, classid, unitidx, scoid)
        if again is not None and again > (result["verified"] or 0):
            result["verified"] = again
    return result''')

open(P, "w", encoding="utf-8").write(src)
print("patch7 ok")
