# -*- coding: utf-8 -*-
"""v3.7 补丁 2：GUI 放开并发（默认 4 路）、预设带路数、预估按路数折算。"""
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


# ── 1. 并发输入：可编辑，默认 4 ──
rep('''        ctk.CTkLabel(thread_row, text="并发数:").pack(side="left")
        self.threads_entry = ctk.CTkEntry(thread_row, width=65, placeholder_text="1")
        self.threads_entry.pack(side="left", padx=5)
        self.threads_entry.insert(0, "1")
        ctk.CTkLabel(thread_row, text="  并发固定 1（票据互斥）",
                     font=ctk.CTkFont(size=10), text_color=("#64748b", "#7c8db5")).pack(side="left")''',
    '''        ctk.CTkLabel(thread_row, text="并发路数:").pack(side="left")
        self.threads_entry = ctk.CTkEntry(thread_row, width=55, placeholder_text="4")
        self.threads_entry.pack(side="left", padx=5)
        self.threads_entry.insert(0, "4")
        ctk.CTkLabel(thread_row, text="  每路各自真实计时，实测 4 路各 +61s/86s 无损耗；建议 3~4，上限 8",
                     font=ctk.CTkFont(size=10), text_color=("#64748b", "#7c8db5")).pack(side="left")''')

# ── 2. 预设增加路数 ──
rep('''        "安全（推荐）": dict(rate=(80, 92), dur=(600, 900), cooldown_every=4,
                         cooldown=(400, 900), cap=24,
                         note="每节课按平台要求学满，每 4 节休息 7~15 分钟，单日最多 24 节。"),
        "标准": dict(rate=(75, 90), dur=(480, 720), cooldown_every=6,
                   cooldown=(120, 300), cap=36,
                   note="节奏略快，风险仍可控；适合课时较少、时间紧的情况。"),
        "极速": dict(rate=(70, 85), dur=(120, 300), cooldown_every=0,
                   cooldown=(0, 0), cap=999,
                   note="⚠ 明显快于平台要求时长，被时钟流速校验/隔天复核打回的概率很高，仅应急用。"),''',
    '''        "安全（推荐）": dict(rate=(80, 92), dur=(600, 900), cooldown_every=4,
                         cooldown=(400, 900), cap=24, lanes=3,
                         note="3 路并行，每路真实学满；每 4 节休息，单日最多 24 节。"),
        "标准": dict(rate=(75, 90), dur=(480, 720), cooldown_every=6,
                   cooldown=(120, 300), cap=36, lanes=4,
                   note="4 路并行，节奏略快；适合课时多、时间紧。"),
        "极速": dict(rate=(70, 85), dur=(120, 300), cooldown_every=0,
                   cooldown=(0, 0), cap=999, lanes=6,
                   note="⚠ 6 路 + 短时长；每节只学到平台要求的一小部分，被复核打回概率很高，仅救急。"),''')

rep('''        self.threads_entry.delete(0, "end")
        self.threads_entry.insert(0, "1")''',
    '''        self.threads_entry.delete(0, "end")
        self.threads_entry.insert(0, str(p.get("lanes", 4)))''')

# ── 3. 预估按路数折算 ──
rep('''        avg = max(1, (lo + hi) // 2)
        cap = min(self.daily_lesson_cap, 999)
        per_day_min = avg * cap / 60.0
        extra = ""
        if self.cooldown_every:
            extra = f"，另加每 {self.cooldown_every} 节约 {self.cooldown_range[0]//60}~" \\
                    f"{self.cooldown_range[1]//60} 分钟休息"
        self.estimate_label.configure(
            text=f"⏱ 单节约 {lo//60}~{hi//60} 分钟；单日上限 {cap} 节 ≈ {per_day_min/60:.1f} 小时{extra}。"
                 f"课时多时请分几天跑，别一次刷完。")''',
    '''        avg = max(1, (lo + hi) // 2)
        cap = min(self.daily_lesson_cap, 999)
        try:
            lanes = max(1, int(self.threads_entry.get()))
        except (ValueError, AttributeError):
            lanes = 4
        per_day_min = avg * cap / 60.0 / lanes
        extra = ""
        if self.cooldown_every:
            extra = f"，另加每 {self.cooldown_every} 节约 {self.cooldown_range[0]//60}~" \\
                    f"{self.cooldown_range[1]//60} 分钟休息"
        self.estimate_label.configure(
            text=f"⏱ 单节约 {lo//60}~{hi//60} 分钟 × {lanes} 路 ⇒ 单日上限 {cap} 节约 "
                 f"{per_day_min/60:.1f} 小时{extra}。课时多时仍建议分几天跑。")''')

# ── 4. 启动校验：并发 1~8，不再强制 1 ──
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
            if want_threads < 1:
                want_threads = 1
            if want_threads > 8:
                want_threads = 8
            if str(want_threads) != self.threads_entry.get():
                self.threads_entry.delete(0, "end")
                self.threads_entry.insert(0, str(want_threads))''')

rep('''            # 线程数（共用）
            max_threads = 1''',
    '''            # 并发路数（共用）
            max_threads = want_threads
            if max_threads > 4:
                self._log(f"[!] {max_threads} 路并行：完成密度会明显高于真人，被平台注意的概率上升",
                          "log_warning")''')

# ── 5. 启动确认文案带路数 ──
rep('''        cap = self.daily_lesson_cap
        est_h = avg_dur * cap / 3600.0''',
    '''        cap = self.daily_lesson_cap
        try:
            lanes = max(1, int(self.threads_entry.get()))
        except (ValueError, AttributeError):
            lanes = 1
        est_h = avg_dur * cap / 3600.0 / lanes''')

rep('''        msg = (f"本次最多处理 {cap} 个课时（单日上限）\\n"
               f"单课时按约 {avg_dur // 60} 分钟计算，满负荷约需 {est_h:.1f} 小时。\\n\\n"''',
    '''        msg = (f"本次最多处理 {cap} 个课时（单日上限），{lanes} 路并行\\n"
               f"单课时按约 {avg_dur // 60} 分钟计算，满负荷约需 {est_h:.1f} 小时。\\n\\n"''')

# ── 6. 风险卡片文案更新 ──
rep('''                     text="平台按「真实在线时长」计学时：单个课时通常要求 18 分钟，"
                          "脚本会自动补齐差额并在提交后回读校验。"
                          "被清记录的主因是「短时间集中完成」，所以默认单并发、单日上限、每几节休息一次。",''',
    '''                     text="平台按「真实在线时长」计学时：单个课时通常要求 18 分钟，脚本自动补齐并在提交后回读校验。"
                          "并行的意义是「同时上 4 节课」——每节仍按真实时间算，只是总墙钟被摊薄 4 倍。"
                          "被清记录的主因是「短时间集中完成」，所以默认 3~4 路、单日上限、每几节休息。",''')

open(P, "w", encoding="utf-8").write(src)
print("patch14 ok")
