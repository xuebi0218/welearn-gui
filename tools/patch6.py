# -*- coding: utf-8 -*-
"""v3.6 补丁 6：刷新失败终态 + 预估初始化 + 帮助页风险说明。"""
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


# 刷新线程：任何失败都要发终态消息，否则控件永久灰死
rep('''        if '\\"clist\\":[]}' in resp.text or '错误' in resp.text:
            app.message_queue.put({"type": "log_error", "text": "会话已过期，请重新登录"})
            return
        courses = resp.json()["clist"]
        app.message_queue.put({"type": "login_success", "courses": courses})
    except Exception as e:
        app.message_queue.put({"type": "log_error", "text": f"刷新课程失败: {e}"})''',
    '''        body = _text(resp)
        if '"clist":[]}' in body or '错误' in body:
            app.message_queue.put({"type": "refresh_fail", "error": "会话已过期，请重新登录"})
            return
        courses = resp.json()["clist"]
        app.message_queue.put({"type": "login_success", "courses": courses})
    except Exception as e:
        app.message_queue.put({"type": "refresh_fail", "error": str(e)})''')

# 主页构建完成后初始化预估文案
rep('''        # ── 日志已移至侧边栏 ──''',
    '''        # 初始化节奏预估文案
        try:
            self._update_estimate()
            self.preset_label.configure(text="当前：安全（推荐）")
        except Exception:
            pass

        # ── 日志已移至侧边栏 ──''')

# 帮助页增加"为什么会被打回"说明
rep('''        # 注意事项
        ctk.CTkLabel(scroll, text="注意事项",''',
    '''        # 为什么会被清记录
        ctk.CTkLabel(scroll, text="为什么刷完当天没事、隔天却被清掉？",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=10, pady=(20, 8))
        reasons = [
            "1. 学时是「真实在线时长」：平台按 startsco→savescoinfo 的墙钟差计时，"
            "单课通常要求 18 分钟。几十秒刷完一节，属于时钟流速异常。",
            "2. 平台按天复核：完成事件当天入库，T+1 再跨事件聚合（完成密度、心跳连续性、登录时间），"
            "命中就整批回滚——这就是「隔天消失」。",
            "3. 并发反而更糟：学习票据（studyTicket）是单账号互斥锁，多开只会互相顶掉、分钟数丢失。",
            "4. 老师端有「学习监控 / 需要关注学生」，正确率 100% 而答题记录缺失很容易被人工清除。",
            "5. 平台还有两道闸门：isPausing（判定刷课行为后锁 N 分钟/今日锁定）、"
            "checkNoCaptcha（强制滑块验证）。本工具会检测到并提示你停下。",
        ]
        for r in reasons:
            ctk.CTkLabel(scroll, text=r, font=ctk.CTkFont(size=12), justify="left",
                         wraplength=760, text_color=("#475569", "#94a3b8")
                         ).pack(anchor="w", padx=10, pady=3)

        ctk.CTkLabel(scroll, text="本工具的做法", font=ctk.CTkFont(size=16, weight="bold")
                     ).pack(anchor="w", padx=10, pady=(16, 8))
        fixes = [
            "• 按平台要求（timelitsec）自动补齐课时时长，不再固定几十秒；",
            "• 学习过程中每 20~32 秒发一次心跳，结束时补心跳，再提交完成，最后回读校验时长；",
            "• 默认单并发、单日上限 24 节、每几节休息一次，模拟真人节奏；",
            "• 正确率默认 80~92% 随机，避免「100% 但没有答题记录」的异常组合；",
            "• 课时多时请分几天跑：学时无法压缩，想拿 6 小时就得真在线 6 小时。",
        ]
        for f in fixes:
            ctk.CTkLabel(scroll, text=f, font=ctk.CTkFont(size=12), justify="left",
                         wraplength=760).pack(anchor="w", padx=10, pady=3)

        # 注意事项
        ctk.CTkLabel(scroll, text="注意事项",''')

# 版本号文案
src = src.replace('"Welearn 刷课工具 v3.5"', '"Welearn 刷课工具 v3.6"')
src = src.replace('当前: v3.5', '当前: v3.6')

open(P, "w", encoding="utf-8").write(src)
print("patch6 ok")
