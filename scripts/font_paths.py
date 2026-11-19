"""Localiza Liberation Sans (pacote fonts-liberation) ou DejaVu."""

from __future__ import annotations

from pathlib import Path

_NAMES = {
    "regular": ("LiberationSans-Regular.ttf", "DejaVuSans.ttf"),
    "bold": ("LiberationSans-Bold.ttf", "DejaVuSans-Bold.ttf"),
}

_DIRS = (
    Path("/usr/share/fonts/truetype/liberation"),
    Path("/usr/share/fonts/truetype/liberation2"),
    Path("/usr/share/fonts/liberation"),
    Path("/usr/share/fonts/truetype/dejavu"),
    Path("/usr/share/fonts/dejavu"),
)


def find_font(kind: str) -> str:
    for folder in _DIRS:
        if not folder.is_dir():
            continue
        for name in _NAMES[kind]:
            path = folder / name
            if path.is_file():
                return str(path)
    raise FileNotFoundError(
        "Fonte Liberation/DejaVu não encontrada. "
        "No Ubuntu: apt-get install -y fonts-liberation"
    )


def liberation_pair() -> tuple[str, str]:
    return find_font("regular"), find_font("bold")
