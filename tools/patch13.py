# -*- coding: utf-8 -*-
"""v3.7 补丁：多路并行（每路独立 Session、独立真实计时）+ GUI 放开发数。"""
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


# ── 1. 会话克隆 + 可中断 sleep ──
rep('''# ── GUI 主类 ──────────────────────────────────────────''',
    '''def _clone_session(src):
    """复制登录态到一个独立 Session。

    requests.Session 的连接池/CookieJar 不是线程安全的，多路并发必须各用各的；
    但 UA 与 Cookie 必须和主会话一致，否则就是「同一账号多个浏览器指纹」。
    """
    s = requests.Session()
    try:
        s.cookies.update(src.cookies.get_dict())
    except Exception:
        pass
    try:
        s.headers['User-Agent'] = _SESSION_PROFILE[0]
    except Exception:
        pass
    return s


def _sleep_interruptible(seconds, stop_check):
    """分段睡眠，停止时能在 1 秒内响应。"""
    waited = 0.0
    while waited < seconds:
        if stop_check():
            return False
        step = min(1.0, seconds - waited)
        time.sleep(step)
        waited += step
    return True


# ── GUI 主类 ──────────────────────────────────────────''')

# ── 2. 刷课：批处理改「多路抢队列」──
rep('''    def process_one(unit_i, course):
        if app.stop_requested:
            return
        loc = course.get("location", "?")
        scoid = course.get("id")
        try:
            blocked, why = welearn_check_gates(app.session, uid, cid)''',
    '''    def process_one(unit_i, course, lane_id=0, session=None):
        if app.stop_requested:
            return
        session = session or app.session
        tag_pre = f"[L{lane_id + 1}] "
        loc = course.get("location", "?")
        scoid = course.get("id")
        try:
            blocked, why = welearn_check_gates(session, uid, cid)''')

rep('''            app.message_queue.put({"type": "log",
                                   "text": f'[刷课] {loc} → 目标正确率 {crate}%，至少学 {dur}s'})
            r = welearn_curriculum_submit(app.session, cid, uid, classid, scoid, crate,''',
    '''            app.message_queue.put({"type": "log",
                                   "text": f'{tag_pre}[刷课] {loc} → 正确率 {crate}%，至少学 {dur}s'})
            r = welearn_curriculum_submit(session, cid, uid, classid, scoid, crate,''')

rep('''            app.message_queue.put({"type": tag, "text": f'  {ok_txt} {sv_txt}｜{detail}'})''',
    '''            app.message_queue.put({"type": tag, "text": f'  {tag_pre}{ok_txt} {sv_txt}｜{detail}'})''')

rep('''        except Exception as e:
            app.message_queue.put({"type": "log_error", "text": f'  ✗ [异常] {loc} - {e}'})''',
    '''        except Exception as e:
            app.message_queue.put({"type": "log_error", "text": f'  {tag_pre}✗ [异常] {loc} - {e}'})''')

old_loop = '''    for start in range(0, total, max_threads):
        if app.stop_requested:
            app.message_queue.put({"type": "log_warning", "text": "⚠️ 用户停止了任务"})
            break
        batch = all_lessons[start:start + max_threads]
        threads = []
        for unit_i, course in batch:
            t = threading.Thread(target=process_one, args=(unit_i, course), daemon=True)
            t.start()
            threads.append(t)
            time.sleep(_rand_delay(0.4, 1.2))
        for t in threads:
            while t.is_alive():
                t.join(timeout=1.0)
        app.message_queue.put({"type": "log",
                               "text": f'✅ 进度 {processed[0]}/{total}｜剩余 {total - processed[0]} 个'})
        # 冷却：每完成若干节休息一段时间，模拟真人节奏
        if cooldown_every and processed[0] < total and processed[0] % cooldown_every == 0:
            rest = random.randint(cooldown_range[0], cooldown_range[1])
            app.message_queue.put({"type": "log",
                                   "text": f'☕ 休息 {rest}s 再继续（降低集中完成特征）'})
            waited = 0
            while waited < rest and not app.stop_requested:
                time.sleep(1.0)
                waited += 1
'''
new_loop = '''    cursor = [0]
    cursor_lock = threading.Lock()

    def next_item():
        with cursor_lock:
            if cursor[0] >= total:
                return None
            item = all_lessons[cursor[0]]
            cursor[0] += 1
            return item

    def lane(lane_id):
        """一路独立浏览器：自己的 Session、自己的心跳节奏，抢剩余课时。"""
        session = _clone_session(app.session)
        time.sleep(random.uniform(0, 12))          # 错峰启动，别让几路同时开始
        done_here = 0
        while not app.stop_requested:
            item = next_item()
            if item is None:
                return
            unit_i, course = item
            process_one(unit_i, course, lane_id, session)
            done_here += 1
            if cooldown_every and done_here % cooldown_every == 0:
                rest = random.randint(cooldown_range[0], cooldown_range[1])
                app.message_queue.put({"type": "log",
                                       "text": f'☕ L{lane_id + 1} 休息 {rest}s（降低集中完成特征）'})
                _sleep_interruptible(rest, lambda: app.stop_requested)

    threads = [threading.Thread(target=lane, args=(i,), daemon=True)
               for i in range(max_threads)]
    for t in threads:
        t.start()
        time.sleep(_rand_delay(0.8, 0.6))
    for t in threads:
        while t.is_alive():
            t.join(timeout=1.0)
    if app.stop_requested:
        app.message_queue.put({"type": "log_warning",
                               "text": f'⚠️ 已停止 | 完成 {processed[0]}/{total}'})
    app.message_queue.put({"type": "log",
                           "text": f'✅ 进度 {processed[0]}/{total}｜剩余 {total - processed[0]} 个'})
'''
rep(old_loop, new_loop)

# ── 3. 刷时长：同样改多路 ──
rep('''def _time_one(app, cid, uid, classid, unit_i, course, learntime, errors, _processed):
    loc = course.get("location", "?")''',
    '''def _time_one(app, cid, uid, classid, unit_i, course, learntime, errors, _processed, session=None):
    session = session or app.session
    loc = course.get("location", "?")''')

src = src.replace("welearn_check_gates(app.session, uid, cid)", "welearn_check_gates(session, uid, cid)")
src = src.replace("cmi = welearn_time_init(app.session, cid, uid, scoid)",
                  "cmi = welearn_time_init(session, cid, uid, scoid)")
src = src.replace('req = welearn_sco_requirements(app.session, cid, uid, classid, scoid)',
                  'req = welearn_sco_requirements(session, cid, uid, classid, scoid)')
src = src.replace('welearn_time_heartbeat(app.session, cid, uid, scoid, "0", str(init_total))',
                  'welearn_time_heartbeat(session, cid, uid, scoid, "0", str(init_total))')

rep('''    for idx in range(0, total, max_threads):
        if app.stop_requested:
            app.message_queue.put({"type": "log_warning", "text": f"⚠️ 已停止 | 进度 {processed}/{total}"})
            break
        batch = all_lessons[idx:idx + max_threads]
        threads = []
        for unit_i, course in batch:
            learn = random.randint(inputtime[0], inputtime[1]) if mode == 2 else int(inputtime)
            t = threading.Thread(target=_time_one, args=(app, cid, uid, classid, unit_i, course,
                                                         learn, errors, lambda: processed),
                                 daemon=True)
            t.start()
            threads.append(t)
            time.sleep(_rand_delay(0.4, 1.2))
        for t in threads:
            while t.is_alive():
                t.join(timeout=1.0)
        processed += len(batch)
        app.message_queue.put({"type": "progress", "current": processed, "total": total})
        app.message_queue.put({"type": "log",
                               "text": f'✅ 进度 {processed}/{total}｜剩余 {total - processed} 个'})''',
    '''    cursor = [0]
    cursor_lock = threading.Lock()
    counter = [0]

    def next_item():
        with cursor_lock:
            if cursor[0] >= total:
                return None
            item = all_lessons[cursor[0]]
            cursor[0] += 1
            return item

    def lane(lane_id):
        session = _clone_session(app.session)
        time.sleep(random.uniform(0, 12))
        while not app.stop_requested:
            item = next_item()
            if item is None:
                return
            unit_i, course = item
            learn = random.randint(inputtime[0], inputtime[1]) if mode == 2 else int(inputtime)
            _time_one(app, cid, uid, classid, unit_i, course, learn, errors,
                      lambda: counter[0], session=session)
            with cursor_lock:
                counter[0] += 1
                cur = counter[0]
            app.message_queue.put({"type": "progress", "current": cur, "total": total})

    threads = [threading.Thread(target=lane, args=(i,), daemon=True)
               for i in range(max_threads)]
    for t in threads:
        t.start()
        time.sleep(_rand_delay(0.8, 0.6))
    for t in threads:
        while t.is_alive():
            t.join(timeout=1.0)
    processed = counter[0]
    app.message_queue.put({"type": "log",
                           "text": f'✅ 进度 {processed}/{total}｜剩余 {total - processed} 个'})''')

# ── 4. 并发上限放宽到 8 ──
src = src.replace("max_threads = _clamp(int(getattr(app, 'curriculum_max_threads', 1) or 1), 1, 3)",
                  "max_threads = _clamp(int(getattr(app, 'curriculum_max_threads', 4) or 4), 1, 8)")
src = src.replace("max_threads = _clamp(int(getattr(app, 'time_max_threads', 1) or 1), 1, 3)",
                  "max_threads = _clamp(int(getattr(app, 'time_max_threads', 4) or 4), 1, 8)")

open(P, "w", encoding="utf-8").write(src)
print("patch13 ok")
