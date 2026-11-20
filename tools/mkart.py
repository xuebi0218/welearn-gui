# -*- coding: utf-8 -*-
"""生成界面素材：鲸鱼娘动效帧 + 渐变横幅。

素材来源：本机开源桌宠 @linxin666/dsh-pet（BSD-3-Clause）的 spritesheet。
- 第 0 行 idle 6 帧 → src/anim_0..5.png（160x160 透明方图，用于侧边栏循环播放）
- 第 3 行 waving 4 帧 → src/wave_0..3.png（备用）
- 渐变横幅 src/banner.png（800x180，深海 → 星云渐变 + 角色立绘 + 气泡）
"""
import os

from PIL import Image, ImageDraw, ImageFilter

ASSETS = r"C:\Users\xuebi\.dsh\profiles\web\.dsh-module-fallback\node_modules\@linxin666\dsh-pet\assets"
SRC_DIR = "src"
CELL_W, CELL_H = 192, 208
FRAMES = [6, 8, 8, 4, 5, 8, 6, 6, 6]      # 各行动画帧数
OUT = 160


def load_sheet(name):
    return Image.open(os.path.join(ASSETS, name, "spritesheet.webp")).convert("RGBA")


def frame(sheet, row, idx):
    return sheet.crop((idx * CELL_W, row * CELL_H, (idx + 1) * CELL_W, (row + 1) * CELL_H))


def square(img, size=OUT, pad=0.96):
    bb = img.split()[3].getbbox()
    if bb:
        img = img.crop(bb)
    scale = (size * pad) / img.height
    img = img.resize((max(1, int(img.width * scale)), int(img.height * scale)), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(img, ((size - img.width) // 2, (size - img.height) // 2), img)
    return canvas


def gradient(size, stops, horizontal=False):
    """线性渐变：stops=[(pos0..1, (r,g,b)), ...]"""
    w, h = size
    img = Image.new("RGB", (1, h) if not horizontal else (w, 1))
    px = img.load()
    n = h if not horizontal else w
    for i in range(n):
        t = i / max(1, n - 1)
        for k in range(len(stops) - 1):
            p0, c0 = stops[k]
            p1, c1 = stops[k + 1]
            if p0 <= t <= p1:
                f = (t - p0) / max(1e-6, p1 - p0)
                c = tuple(int(c0[j] + (c1[j] - c0[j]) * f) for j in range(3))
                break
        else:
            c = stops[-1][1]
        if horizontal:
            px[i, 0] = c
        else:
            px[0, i] = c
    return img.resize((w, h), Image.BILINEAR)


def main():
    os.makedirs(SRC_DIR, exist_ok=True)
    refined = load_sheet("whale-refined")

    # 1) idle 动效帧
    for i in range(FRAMES[0]):
        square(frame(refined, 0, i)).save(os.path.join(SRC_DIR, f"anim_{i}.png"), optimize=True)
    # 2) waving 帧（备用图集）
    for i in range(FRAMES[3]):
        square(frame(refined, 3, i)).save(os.path.join(SRC_DIR, f"wave_{i}.png"), optimize=True)

    # 3) 渐变横幅
    W, H = 800, 190
    bg = gradient((W, H), [(0.0, (10, 18, 38)), (0.45, (26, 42, 92)),
                           (0.78, (46, 92, 128)), (1.0, (18, 30, 60))], horizontal=True)

    # 柔和光斑
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((W * 0.52, -H * 0.7, W * 1.05, H * 1.4), fill=(64, 196, 200))
    gd.ellipse((-W * 0.1, H * 0.35, W * 0.42, H * 1.6), fill=(70, 88, 200))
    glow = glow.filter(ImageFilter.GaussianBlur(58))
    bg = Image.blend(bg, glow, 0.32)

    # 细气泡
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    import random
    random.seed(7)
    for _ in range(26):
        r = random.uniform(1.5, 5.0)
        x = random.uniform(0, W)
        y = random.uniform(0, H)
        a = random.randint(24, 78)
        ld.ellipse((x - r, y - r, x + r, y + r), outline=(190, 235, 255, a), width=1)

    # 角色立绘（waving 第 0 帧），右对齐放在光斑里
    hero = square(frame(refined, 3, 0), size=176, pad=1.0)
    hx = W - hero.width - 18
    hy = max(0, (H - hero.height) // 2 + 4)

    # 角色下方柔光
    halo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    hd = ImageDraw.Draw(halo)
    hd.ellipse((hx + hero.width * 0.12, H * 0.42, hx + hero.width * 0.92, H * 1.06),
               fill=(120, 220, 235, 70))
    halo = halo.filter(ImageFilter.GaussianBlur(26))

    out = bg.convert("RGBA")
    out = Image.alpha_composite(out, halo)
    out = Image.alpha_composite(out, layer)
    out.alpha_composite(hero, (hx, hy))
    # 4) 标题烘焙进图里（避免控件叠字出现色块）
    from PIL import ImageFont
    d = ImageDraw.Draw(out)
    f_title = ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc", 34)
    f_sub = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 15)
    d.text((34, 52), "WE·LEARN 学习助手", font=f_title, fill=(244, 249, 255, 255))
    d.text((36, 100), "按平台要求补齐学时 · 多路并行 · 提交后回读校验",
           font=f_sub, fill=(168, 199, 232, 255))

    out.save(os.path.join(SRC_DIR, "banner.png"), optimize=True)

    # 5) 细渐变条（页面顶部装饰，无文字，随宽度拉伸）
    strip = gradient((800, 10), [(0.0, (86, 214, 214)), (0.42, (86, 132, 235)),
                                 (0.74, (124, 110, 230)), (1.0, (198, 168, 108))], horizontal=True)
    strip.save(os.path.join(SRC_DIR, "strip.png"), optimize=True)

    print("assets ok:", sorted(f for f in os.listdir(SRC_DIR) if f.startswith(("anim_", "wave_", "banner"))))


if __name__ == "__main__":
    main()
