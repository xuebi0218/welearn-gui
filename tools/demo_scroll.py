# -*- coding: utf-8 -*-
"""真实窗口 + 自动滚到进度区，并把 canvas 状态写到 tools/_scroll.log 便于核对。"""
import os
import sys

sys.path.insert(0, "src")
import welearn_gui as wg   # noqa: E402

app = wg.WelearnApp()
app.root.title(f"Welearn 刷课工具 v4.0 · demo{os.getpid()}")


def probe():
    c = app.home_scroll._parent_canvas
    lines = []
    lines.append("root=%sx%s" % (app.root.winfo_width(), app.root.winfo_height()))
    lines.append("content=%sx%s page=%sx%s hs=%sx%s canvas=%sx%s region=%s yview=%s" % (
        app.content_area.winfo_width(), app.content_area.winfo_height(),
        app.pages["home"].winfo_width(), app.pages["home"].winfo_height(),
        app.home_scroll.winfo_width(), app.home_scroll.winfo_height(),
        c.winfo_width(), c.winfo_height(), c.cget("scrollregion"), c.yview()))
    c.yview_moveto(1.0)
    app.root.update_idletasks()
    lines.append("after moveto yview=%s" % (c.yview(),))
    app._scroll_to_progress()
    app.root.update_idletasks()
    lines.append("after _scroll_to_progress yview=%s" % (c.yview(),))
    with open("tools/_scroll.log", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


app.root.after(1500, probe)
app.root.after(45000, app.root.destroy)
app.root.mainloop()
