# -*- coding: utf-8 -*-
"""v4.0 补丁 24：单节上限挪到「时长与并发」区（设置项不该藏在进度区）。"""
import sys

P = "src/welearn_gui.py"
src = open(P, encoding="utf-8").read()

cap_block = '''        # 单节上限
        cap_row = ctk.CTkFrame(progress_frame, fg_color="transparent")
        cap_row.pack(fill="x", pady=(6, 0))
        ctk.CTkLabel(cap_row, text="单节上限:", font=ctk.CTkFont(size=11)).pack(side="left")
        self.cap_menu = ctk.CTkOptionMenu(cap_row, values=["10 分钟", "15 分钟", "20 分钟", "30 分钟", "不设上限"],
                                          width=110, height=26, font=ctk.CTkFont(size=11),
                                          command=self._on_cap_change)
        self.cap_menu.pack(side="left", padx=6)
        _cap = int(getattr(self, "lesson_cap", 1200) or 0)
        self.cap_menu.set(f"{_cap // 60} 分钟" if _cap else "不设上限")
        ctk.CTkLabel(cap_row, text="（平台要求 30 分钟时，超限就下次再补，更像真人）",
                     font=ctk.CTkFont(size=10), text_color=("#64748b", "#7c8db5")).pack(side="left")

'''
if src.count(cap_block) != 1:
    print("MISMATCH cap block", src.count(cap_block))
    sys.exit(1)
src = src.replace(cap_block, "")

anchor = '''        ctk.CTkLabel(thread_row, text="（每路各自真实计时：实测 4 路各 +61s/86s 无损耗；建议 3~4，上限 8）",
                     font=ctk.CTkFont(size=10), text_color=("#64748b", "#7c8db5")).pack(side="left")
'''
if src.count(anchor) != 1:
    print("MISMATCH anchor", src.count(anchor))
    sys.exit(1)

new_anchor = anchor + '''
        cap_row = ctk.CTkFrame(shared_panel, fg_color="transparent")
        cap_row.pack(fill="x", pady=(8, 0))
        ctk.CTkLabel(cap_row, text="单节上限:", font=ctk.CTkFont(size=11)).pack(side="left")
        self.cap_menu = ctk.CTkOptionMenu(cap_row, values=["10 分钟", "15 分钟", "20 分钟", "30 分钟", "不设上限"],
                                          width=110, height=26, font=ctk.CTkFont(size=11),
                                          command=self._on_cap_change)
        self.cap_menu.pack(side="left", padx=6)
        _cap = int(getattr(self, "lesson_cap", 1200) or 0)
        self.cap_menu.set(f"{_cap // 60} 分钟" if _cap else "不设上限")
        ctk.CTkLabel(cap_row, text="（平台要 30 分钟时，超限这一段就停，下次接着补）",
                     font=ctk.CTkFont(size=10), text_color=("#64748b", "#7c8db5")).pack(side="left")
'''
src = src.replace(anchor, new_anchor)

open(P, "w", encoding="utf-8").write(src)
print("patch24 ok")
