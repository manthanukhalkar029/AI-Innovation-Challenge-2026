"""
Subject-aware slide rendering (requirement #10): picks a different diagram
style depending on the lesson section's `visual_type` (set by the lesson
planner): equations+graphs for maths, labeled diagrams for biology,
timelines for history, syntax-highlighted code + flow for programming, and
a generic concept illustration otherwise.
"""
import os
import re
import textwrap
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .avatar import render_avatar

W, H = 1280, 720
BG = (18, 22, 30)
PANEL = (28, 34, 46)
ACCENT = (86, 180, 255)
TEXT = (235, 238, 242)
SUBTLE = (150, 160, 175)


def _font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for c in candidates:
        if os.path.exists(c):
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


def _wrap_draw(d, text, box, font, fill, line_spacing=8):
    x, y, max_w, _ = box
    avg_char_w = font.getbbox("x")[2] - font.getbbox("x")[0] or 8
    wrap_width = max(10, int(max_w / max(avg_char_w, 1)))
    lines = textwrap.wrap(text, width=wrap_width)
    for line in lines:
        d.text((x, y), line, font=font, fill=fill)
        y += font.size + line_spacing
    return y


def _diagram_area(visual_type: str, title: str, explanation: str) -> Image.Image:
    """Returns an RGBA image (900x420) for the main visual panel, style
    chosen by subject/visual_type."""
    size = (900, 420)
    if visual_type == "equation_graph":
        return _render_equation_graph(title, size)
    if visual_type == "diagram_simulation":
        return _render_process_diagram(title, explanation, size)
    if visual_type == "labeled_diagram":
        return _render_labeled_diagram(title, explanation, size)
    if visual_type == "timeline_map":
        return _render_timeline(title, explanation, size)
    if visual_type == "code_execution":
        return _render_code_panel(title, explanation, size)
    return _render_concept_illustration(title, explanation, size)


def _fig_to_image(fig, size):
    fig.canvas.draw()
    buf = np.asarray(fig.canvas.buffer_rgba())
    img = Image.fromarray(buf).convert("RGBA").resize(size)
    plt.close(fig)
    return img


def _render_equation_graph(title, size):
    fig, ax = plt.subplots(figsize=(size[0] / 100, size[1] / 100), dpi=100)
    fig.patch.set_facecolor("#1c222e")
    ax.set_facecolor("#1c222e")
    x = np.linspace(-5, 5, 200)
    y = np.sin(x) if "trig" in title.lower() else x ** 2 / 4
    ax.plot(x, y, color="#56b4ff", linewidth=3)
    ax.axhline(0, color="#556", linewidth=1)
    ax.axvline(0, color="#556", linewidth=1)
    ax.tick_params(colors="#aab")
    for spine in ax.spines.values():
        spine.set_color("#445")
    ax.set_title(title, color="white", fontsize=13)
    return _fig_to_image(fig, size)


def _render_timeline(title, explanation, size):
    fig, ax = plt.subplots(figsize=(size[0] / 100, size[1] / 100), dpi=100)
    fig.patch.set_facecolor("#1c222e")
    ax.set_facecolor("#1c222e")
    ax.axhline(0.5, color="#56b4ff", linewidth=3)
    n = 5
    for i in range(n):
        xpos = (i + 1) / (n + 1)
        ax.scatter([xpos], [0.5], s=140, color="#f2a341", zorder=3)
        ax.text(xpos, 0.62, f"Event {i+1}", color="white", ha="center", fontsize=10)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_title(title, color="white", fontsize=13)
    return _fig_to_image(fig, size)


def _render_process_diagram(title, explanation, size):
    img = Image.new("RGBA", size, (28, 34, 46, 255))
    d = ImageDraw.Draw(img)
    steps = re.split(r"[.;]\s+", explanation)[:4] or ["Step"]
    steps = [s.strip() for s in steps if s.strip()][:4] or ["Concept"]
    box_w = size[0] // len(steps) - 30
    y = size[1] // 2 - 50
    for i, step in enumerate(steps):
        x = 20 + i * (box_w + 30)
        d.rounded_rectangle([x, y, x + box_w, y + 100], radius=14,
                             outline=(86, 180, 255), width=3, fill=(38, 46, 62, 255))
        _wrap_draw(d, step[:60], (x + 12, y + 14, box_w - 24, 90), _font(15), TEXT)
        if i < len(steps) - 1:
            ax = x + box_w + 4
            d.line([ax, y + 50, ax + 22, y + 50], fill=(242, 163, 65), width=4)
            d.polygon([(ax + 22, y + 42), (ax + 22, y + 58), (ax + 32, y + 50)], fill=(242, 163, 65))
    d.text((20, 20), title, font=_font(22, bold=True), fill=TEXT)
    return img


def _render_labeled_diagram(title, explanation, size):
    img = Image.new("RGBA", size, (28, 34, 46, 255))
    d = ImageDraw.Draw(img)
    cx, cy, r = size[0] // 2, size[1] // 2 + 10, 130
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=ACCENT, width=4)
    labels = re.findall(r"[A-Z][a-z]{3,}", explanation)[:4] or ["Structure"]
    for i, label in enumerate(labels):
        angle = (i / max(len(labels), 1)) * 2 * np.pi
        lx, ly = cx + int(r * 1.4 * np.cos(angle)), cy + int(r * 1.4 * np.sin(angle))
        px, py = cx + int(r * np.cos(angle)), cy + int(r * np.sin(angle))
        d.line([px, py, lx, ly], fill=SUBTLE, width=2)
        d.ellipse([px - 5, py - 5, px + 5, py + 5], fill=(242, 163, 65))
        d.text((lx - 30, ly - 8), label, font=_font(16), fill=TEXT)
    d.text((20, 20), title, font=_font(22, bold=True), fill=TEXT)
    return img


def _render_code_panel(title, explanation, size):
    img = Image.new("RGBA", size, (16, 18, 24, 255))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, size[0], 36], fill=(40, 44, 54))
    for i, c in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        d.ellipse([16 + i * 22, 12, 30 + i * 22, 26], fill=c)
    mono = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
    font = ImageFont.truetype(mono, 16) if os.path.exists(mono) else _font(16)
    snippet = [
        f"# {title}",
        "def solve(input_data):",
        "    result = process(input_data)",
        "    return result",
        "",
        "output = solve(sample)",
        "print(output)  # -> matches expected behavior",
    ]
    y = 55
    for line in snippet:
        color = (110, 200, 130) if line.strip().startswith("#") else (220, 224, 230)
        d.text((24, y), line, font=font, fill=color)
        y += 26
    return img


def _render_concept_illustration(title, explanation, size):
    img = Image.new("RGBA", size, (28, 34, 46, 255))
    d = ImageDraw.Draw(img)
    cx, cy = size[0] // 2, size[1] // 2 - 20
    d.ellipse([cx - 90, cy - 90, cx + 90, cy + 90], outline=ACCENT, width=6)
    d.ellipse([cx - 45, cy - 45, cx + 45, cy + 45], fill=(242, 163, 65))
    d.text((20, 20), title, font=_font(22, bold=True), fill=TEXT)
    _wrap_draw(d, explanation, (60, cy + 120, size[0] - 120, 100), _font(16), SUBTLE)
    return img


def render_slide(section: dict, mouth_open: bool, caption: str = None) -> Image.Image:
    """Composes: header bar, subject-aware diagram panel, avatar with the
    given mouth state, and a burned-in caption strip (on-screen text
    requirement)."""
    slide = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(slide)

    d.rectangle([0, 0, W, 84], fill=(14, 17, 23))
    d.text((36, 24), section.get("title", ""), font=_font(30, bold=True), fill=ACCENT)

    diagram = _diagram_area(section.get("visual_type", "concept_illustration"),
                             section.get("title", ""), section.get("explanation", ""))
    slide.paste(diagram.convert("RGB"), (30, 110))

    avatar_img = render_avatar(mouth_open)
    slide.paste(avatar_img, (960, 110), avatar_img)
    d.rounded_rectangle([950, 440, 1250, 470], radius=10, fill=PANEL)
    d.text((965, 447), "AI Teacher", font=_font(15, bold=True), fill=TEXT)

    d.rectangle([0, H - 150, W, H], fill=(12, 14, 19))
    cap = caption if caption is not None else section.get("explanation", "")
    _wrap_draw(d, cap, (36, H - 132, W - 72, 130), _font(20), TEXT, line_spacing=6)

    return slide
