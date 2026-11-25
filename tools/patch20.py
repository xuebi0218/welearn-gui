# -*- coding: utf-8 -*-
"""v3.9 补丁 20：题目解析补全（et-blank 的全部写法 + notscored 标注）。"""
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


rep('''    questions = []

    # ── 填空: <et-blank g>答案</et-blank> ──
    for m in re.finditer(r'<et-blank\\s+g>(.*?)</et-blank>', html, re.DOTALL):
        answer = m.group(1).strip()
        answer = re.sub(r'<[^>]+>', '', answer)
        answer = unescape(answer).strip()
        if answer:
            questions.append({'type': 'blank', 'answer': answer})

    # ── 判断: <et-tof key="t|f"> ──
    for m in re.finditer(r'<et-tof\\s+key="([tf])"', html, re.DOTALL):
        questions.append({'type': 'tof', 'answer': m.group(1)})

    # ── 选择: <et-choice key="..."> ──
    for m in re.finditer(r'<et-choice[^>]*key="([^"]*)"', html, re.DOTALL):
        questions.append({'type': 'choice', 'answer': m.group(1)})

    return questions''',
    '''    questions = []

    # ── 填空：<et-blank ...>答案</et-blank> ──
    # 平台有四种写法：g / g notscored / noinput g / notscored multiline ... g
    # 旧版只认 "<et-blank g>"，把 40/89 的填空（含 notscored）全漏掉了。
    for m in re.finditer(r'<et-blank([^>]*)>(.*?)</et-blank>', html, re.DOTALL):
        attrs, body = m.group(1), m.group(2)
        if 'noinput' in attrs:
            continue
        answer = re.sub(r'<[^>]+>', '', body)
        answer = unescape(answer).strip()
        if not answer:
            continue
        questions.append({'type': 'blank', 'answer': answer,
                          'scored': 'notscored' not in attrs})

    # ── 判断: <et-tof key="t|f"> ──
    for m in re.finditer(r'<et-tof\\s+key="([tf])"', html, re.DOTALL):
        questions.append({'type': 'tof', 'answer': m.group(1), 'scored': True})

    # ── 选择: <et-choice key="..."> ──
    for m in re.finditer(r'<et-choice[^>]*key="([^"]*)"', html, re.DOTALL):
        questions.append({'type': 'choice', 'answer': m.group(1), 'scored': True})

    # ── 开关/排序类: <et-select key="..."> ──
    for m in re.finditer(r'<et-select[^>]*key="([^"]*)"', html, re.DOTALL):
        questions.append({'type': 'choice', 'answer': m.group(1), 'scored': True})

    return questions''')

# 未计分题按 neutral 提交，别把"开放式题"伪装成答对
rep('''    for i, q in enumerate(questions):
        is_correct = random.random() * 100 < crate''',
    '''    for i, q in enumerate(questions):
        scored = q.get('scored', True)
        is_correct = scored and random.random() * 100 < crate''')

rep('''        else:
            continue

        # SCORM interactions 对象''',
    '''        else:
            continue
        if not scored:
            learner_response = q['answer']
            result = 'neutral'

        # SCORM interactions 对象''')

rep('''        if is_correct:
            scorm_obj['correct_responses'] = [{'pattern': q['answer']}]''',
    '''        if is_correct or not scored:
            scorm_obj['correct_responses'] = [{'pattern': q['answer']}]''')

open(P, "w", encoding="utf-8").write(src)
print("patch20 ok")
