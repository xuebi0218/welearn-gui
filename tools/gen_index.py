# -*- coding: utf-8 -*-
"""从 AST 重新生成 CLAUDE.md 的行号速查表。"""
import ast
import re

P = "src/welearn_gui.py"
src = open(P, encoding="utf-8").read()
tree = ast.parse(src)

rows = []
for node in tree.body:
    if isinstance(node, ast.FunctionDef):
        rows.append((node.lineno, node.name, "函数"))
    elif isinstance(node, ast.ClassDef):
        rows.append((node.lineno, node.name, "类"))
        for sub in node.body:
            if isinstance(sub, ast.FunctionDef):
                rows.append((sub.lineno, "." + sub.name, "方法"))
rows.sort()
total = len(src.splitlines())

lines = ["| 行号 | 名称 | 类型 |", "|------|------|------|"]
for line, name, kind in rows:
    lines.append(f"| {line} | `{name}` | {kind} |")
table = "\n".join(lines)

cm = open("CLAUDE.md", encoding="utf-8").read()
start = cm.index("### 行号速查表")
m = re.search(r"\n## ", cm[start:])
end = start + m.start() if m else len(cm)

new_section = (
    "### 行号速查表（自动生成，v3.6）\n\n"
    f"主文件共 **{total}** 行。索引由 `tools/gen_index.py` 从 AST 生成，改代码后重新生成。\n\n"
    + table + "\n\n"
)
cm = cm[:start] + new_section + cm[end:]

cm = cm.replace("Welearn 刷课工具 GUI v3.4 — CustomTkinter 桌面应用。",
                "Welearn 刷课工具 GUI v3.6 — CustomTkinter 桌面应用。")
cm = cm.replace(
    "- **主文件**: `src/welearn_gui.py` (~1800行，唯一需要修改的文件)",
    "- **主文件**: `src/welearn_gui.py`（唯一需要修改的文件）\n"
    "- **风险分析**: `docs/RISK_ANALYSIS.md`（打回原因 + 对策，必读）\n"
    "- **变更日志**: `docs/CHANGELOG_v3.6.md`")

help3 = '  --add-data "src/help_3.jpg;src/" ' + chr(92)
if help3 in cm and "mascot.png" not in cm:
    cm = cm.replace(help3, help3 + "\n" + '  --add-data "src/mascot.png;src/" ' + chr(92))

pilimg = "  --hidden-import PIL.Image " + chr(92)
if pilimg in cm and "brotli" not in cm:
    cm = cm.replace(pilimg, pilimg + "\n  --hidden-import brotli " + chr(92))

open("CLAUDE.md", "w", encoding="utf-8").write(cm)
print("CLAUDE.md updated; entries:", len(rows), "lines:", total)
