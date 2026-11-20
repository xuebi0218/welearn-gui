# -*- coding: utf-8 -*-
"""v3.7 补丁 14b：按实际文本替换并发控件（排版与 patch14 假设不同）。"""
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


rep('''        ctk.CTkLabel(thread_row, text="并发数:").pack(side="left")
        self.threads_entry = ctk.CTkEntry(thread_row, width=65, placeholder_text="1")
        self.threads_entry.pack(side="left", padx=5)
        self.threads_entry.insert(0, "1")
        ctk.CTkLabel(thread_row, text="（同账号只能 1，多个会因学习票据互踢而丢失时长）",
                     font=ctk.CTkFont(size=10), text_color=("#64748b", "#7c8db5")).pack(side="left")''',
    '''        ctk.CTkLabel(thread_row, text="并发路数:").pack(side="left")
        self.threads_entry = ctk.CTkEntry(thread_row, width=55, placeholder_text="4")
        self.threads_entry.pack(side="left", padx=5)
        self.threads_entry.insert(0, "4")
        ctk.CTkLabel(thread_row, text="（每路各自真实计时：实测 4 路各 +61s/86s 无损耗；建议 3~4，上限 8）",
                     font=ctk.CTkFont(size=10), text_color=("#64748b", "#7c8db5")).pack(side="left")''')

# 侧边预设行里的旧文案
rep('''        ctk.CTkLabel(preset_row, text="  并发固定 1（票据互斥）",''',
    '''        ctk.CTkLabel(preset_row, text="  并行 = 同时上多节课，每节仍按真实时间算",''')

# 启动校验
rep('''            # 并发：同账号票据互斥，强制 1''',
    '''            # 并发路数：1~8''')
rep('''            try:
                want_threads = int(self.threads_entry.get())
            except (ValueError, AttributeError):
                want_threads = 1
            if want_threads != 1:
                self.threads_entry.delete(0, "end")
                self.threads_entry.insert(0, "1")
                self._log("[!] 并发已强制改为 1：同账号多个课时会互相顶掉学习票据，反而丢时长", "log_warning")''',
    '''            try:
                want_threads = int(self.threads_entry.get())
            except (ValueError, AttributeError):
                want_threads = 4
            want_threads = max(1, min(8, want_threads))
            if str(want_threads) != self.threads_entry.get():
                self.threads_entry.delete(0, "end")
                self.threads_entry.insert(0, str(want_threads))''')

rep('''            # 线程数（共用）
            max_threads = 1''',
    '''            # 并发路数（共用）
            max_threads = want_threads
            if max_threads > 4:
                self._log(f"[!] {max_threads} 路并行：完成密度明显高于真人，被平台注意的概率上升",
                          "log_warning")''')

open(P, "w", encoding="utf-8").write(src)
print("patch14b ok")
