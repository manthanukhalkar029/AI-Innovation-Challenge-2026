"""
Assembles a lesson plan into an actual .mp4 teaching video: per-section
narration audio, a subject-aware slide with a talking avatar, and a
subtitle strip - then concatenates all sections into one lesson video.

This runs with zero external services (ffmpeg only), which is what makes
"Task 1: AI Teaching Video" demoable without any paid API. Swap in a real
TTS/avatar provider (see tts.py, avatar.py) for production quality without
touching this assembly logic.
"""
import os
import shutil
import subprocess
import tempfile

from .slides import render_slide
from .tts import narrate, audio_duration

FRAME_RATE = 2  # mouth toggles per second - a deliberately simple lip-sync cue


def _build_section_clip(section: dict, workdir: str, index: int) -> str:
    narration_text = f"{section.get('title', '')}. {section.get('explanation', '')} " \
                      f"For example, {section.get('example', '')}"
    audio_path = os.path.join(workdir, f"sec{index}_audio.wav")
    narrate(narration_text, section.get("_language", "English"), audio_path)
    duration = audio_duration(audio_path)

    closed = render_slide(section, mouth_open=False)
    opened = render_slide(section, mouth_open=True)
    closed_path = os.path.join(workdir, f"sec{index}_closed.png")
    opened_path = os.path.join(workdir, f"sec{index}_open.png")
    closed.save(closed_path)
    opened.save(opened_path)

    n_frames = max(2, round(duration * FRAME_RATE))
    frame_dir = os.path.join(workdir, f"frames_{index}")
    os.makedirs(frame_dir, exist_ok=True)
    for i in range(n_frames):
        src = opened_path if i % 2 == 0 else closed_path
        shutil.copy(src, os.path.join(frame_dir, f"frame_{i:04d}.png"))

    clip_path = os.path.join(workdir, f"sec{index}_clip.mp4")
    subprocess.run([
        "ffmpeg", "-y",
        "-framerate", str(FRAME_RATE), "-i", os.path.join(frame_dir, "frame_%04d.png"),
        "-i", audio_path,
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest",
        clip_path,
    ], check=True, capture_output=True)
    return clip_path


def build_lesson_video(lesson: dict, out_path: str) -> str:
    with tempfile.TemporaryDirectory() as workdir:
        clip_paths = []
        for i, section in enumerate(lesson.get("sections", [])):
            section = dict(section)
            section["_language"] = lesson.get("language", "English")
            clip_paths.append(_build_section_clip(section, workdir, i))

        concat_list = os.path.join(workdir, "concat.txt")
        with open(concat_list, "w") as f:
            for p in clip_paths:
                f.write(f"file '{p}'\n")

        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", concat_list, "-c", "copy", out_path,
        ], check=True, capture_output=True)

    return out_path
