"""Render this exported Gemini chapter pack.

Set GEMINI_API_KEY first, then run:
    python render_chapter.py
"""

from pathlib import Path
import subprocess
import sys


MODEL = 'gemini-2.5-pro-preview-tts'
MANIFEST = Path(__file__).with_name("manifest.json")


def main() -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "src.aura.gemini_chapter_renderer",
            "--manifest",
            MANIFEST,
            "--model",
            MODEL,
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
