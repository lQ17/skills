import os, random
from PIL import Image, ImageDraw, ImageFont

# 高熵随机字符集（去掉易混淆的 O/0/1/I，提升视觉可读性）
CHARSET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
secret = "".join(random.choices(CHARSET, k=10))

here = os.path.dirname(os.path.abspath(__file__))
out = os.path.join(here, "canary.png")

W, H = 520, 150
img = Image.new("RGB", (W, H), "white")
d = ImageDraw.Draw(img)
font = None
for cand in ["C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/DejaVuSans.ttf"]:
    try:
        font = ImageFont.truetype(cand, 56)
        break
    except Exception:
        continue
if font is None:
    font = ImageFont.load_default()

bbox = d.textbbox((0, 0), secret, font=font)
tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
x = (W - tw) / 2 - bbox[0]
y = (H - th) / 2 - bbox[1]
d.text((x, y), secret, fill="black", font=font)
img.save(out)
# 只打印元数据，绝不把密钥本身写进任何文本
print("CANARY_WRITTEN", out, os.path.getsize(out), "bytes")
