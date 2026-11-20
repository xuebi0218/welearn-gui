# -*- coding: utf-8 -*-
"""v3.7 补丁 15：预设带路数、预估按路数折算、确认框带路数、文案更新。"""
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
                   note="⚠ 6 路 + 短时长；每节没学够平台要求，被复核打回概率很高，仅救急。"),''')

rep('''        self.threads_entry.delete(0, "end")
        self.threads_entry.insert(0, "1")''',
    '''        self.threads_entry.delete(0, "end")
        self.threads_entry.insert(0, str(p.get("lanes", 4)))''')

rep('''        per_day_min = avg * cap / 60.0
        extra = ""
        if self.cooldown_every:
            extra = f"，另加每 {self.cooldown_every} 节约 {self.cooldown_range[0]//60}~" \\
                    f"{self.cooldown_range[1]//60} 分钟休息"
        self.estimate_label.configure(
            text=f"⏱ 单节约 {lo//60}~{hi//60} 分钟；单日上限 {cap} 节 ≈ {per_day_min/60:.1f} 小时{extra}。"
                 f"课时多时请分几天跑，别一次刷完。")''',
    '''        try:
            lanes = max(1, int(self.threads_entry.get()))
        except (ValueError, AttributeError):
            lanes = 4
        per_day_min = avg * cap / 60.0 / lanes
        extra = ""
        if self.cooldown_every:
            extra = f"，另加每 {self.cooldown_every} 节约 {self.cooldown_range[0]//60}~" \\
                    f"{self.cooldown_range[1]//60} 分钟休息"
        self.estimate_label.configure(
            text=f"⏱ 单节约 {lo//60}~{hi//60} 分钟 × {lanes} 路 ⇒ 单日 {cap} 节约 "
                 f"{per_day_min/60:.1f} 小时{extra}。课时多仍建议分几天跑。")''')

rep('''        cap = self.daily_lesson_cap
        est_h = avg_dur * cap / 3600.0
        msg = (f"本次最多处理 {cap} 个课时（单日上限）\\n"''',
    '''        cap = self.daily_lesson_cap
        try:
            lanes = max(1, int(self.threads_entry.get()))
        except (ValueError, AttributeError):
            lanes = 1
        est_h = avg_dur * cap / 3600.0 / lanes
        msg = (f"本次最多处理 {cap} 个课时（单日上限），{lanes} 路并行\\n"''')

rep('''                          "被清记录的主因是「短时间集中完成」，所以默认单并发、单日上限、每几节休息一次。",''',
    '''                          "并行的意义是「同时上 4 节课」——每节仍按真实时间算，只是总墙钟被摊薄 4 倍。"
                          "被清记录的主因是「短时间集中完成」，所以默认 3~4 路、单日上限、每几节休息。",''')

# 帮助页里的两处旧结论（并发互斥 / 默认单并发）
rep('''            "3. 并发反而更糟：学习票据（studyTicket）是单账号互斥锁，多开只会互相顶掉、分钟数丢失。",''',
    '''            "3. studyTicket 互踢只在浏览器 JS 里生效（多开会弹框并 EndSCO）；纯发包不受影响，"
            "实测 4 路并行各 +61s/86s、零损耗——所以并行是合法的提速手段，代价是完成密度更像脚本。",''')
rep('''            "• 默认单并发、单日上限 24 节、每几节休息一次，模拟真人节奏；",''',
    '''            "• 默认 3~4 路并行（每路真实计时）+ 单日上限 + 每几节休息，兼顾速度与痕迹；",''')

open(P, "w", encoding="utf-8").write(src)
print("patch15 ok")
