"""
Draws a small, clean 2D vector avatar (no external assets, no GPU, no paid
API) with two mouth states so the assembled video shows a talking teacher
rather than a static portrait.

This is deliberately simple - it exists so the project **runs and produces
a real .mp4 out of the box**. docs/ARCHITECTURE.md documents exactly where
to swap this for a production photoreal talking-head service (D-ID, HeyGen,
Synthesia, SadTalker/Wav2Lip if self-hosting) behind the same
`render_avatar(mouth_state)` call.
"""
from PIL import Image, ImageDraw

SKIN = (240, 200, 165)
HAIR = (60, 45, 40)
SHIRT = (50, 110, 170)
OUTLINE = (30, 30, 30)


def render_avatar(mouth_open: bool, size=(260, 320)) -> Image.Image:
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    w, h = size
    cx = w // 2

    # shoulders / shirt
    d.rounded_rectangle([cx - 90, h - 90, cx + 90, h], radius=30, fill=SHIRT)
    # neck
    d.rectangle([cx - 20, h - 130, cx + 20, h - 70], fill=SKIN)
    # head
    head_top, head_bottom = 40, 230
    d.ellipse([cx - 75, head_top, cx + 75, head_bottom], fill=SKIN, outline=OUTLINE, width=3)
    # hair
    d.pieslice([cx - 78, head_top - 25, cx + 78, head_top + 70], 180, 360, fill=HAIR)
    # eyes
    d.ellipse([cx - 40, 120, cx - 20, 138], fill=(255, 255, 255), outline=OUTLINE)
    d.ellipse([cx + 20, 120, cx + 40, 138], fill=(255, 255, 255), outline=OUTLINE)
    d.ellipse([cx - 33, 124, cx - 25, 134], fill=(30, 30, 30))
    d.ellipse([cx + 27, 124, cx + 35, 134], fill=(30, 30, 30))
    # eyebrows
    d.line([cx - 42, 112, cx - 18, 108], fill=OUTLINE, width=3)
    d.line([cx + 18, 108, cx + 42, 112], fill=OUTLINE, width=3)
    # nose
    d.line([cx, 138, cx - 6, 165], fill=OUTLINE, width=2)
    # mouth: two states approximate crude lip-sync
    if mouth_open:
        d.ellipse([cx - 22, 178, cx + 22, 205], fill=(150, 60, 60), outline=OUTLINE, width=2)
    else:
        d.line([cx - 20, 188, cx + 20, 188], fill=OUTLINE, width=4)

    return img


def save_pair(out_dir: str):
    import os
    os.makedirs(out_dir, exist_ok=True)
    closed = os.path.join(out_dir, "avatar_closed.png")
    open_ = os.path.join(out_dir, "avatar_open.png")
    render_avatar(False).save(closed)
    render_avatar(True).save(open_)
    return closed, open_
