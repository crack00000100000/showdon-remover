# -*- coding: utf-8 -*-
"""
icon.svg → icon.icns 변환 (VSR).

PySide6 의 QSvgRenderer 로 다중 사이즈 PNG 를 렌더링한 뒤
macOS 의 iconutil 로 .icns 패키지를 만든다.

사용:
    python design/make_icns.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSize, Qt, QByteArray
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


ICONSET_SIZES = [
    (16, 1, "icon_16x16.png"),
    (16, 2, "icon_16x16@2x.png"),
    (32, 1, "icon_32x32.png"),
    (32, 2, "icon_32x32@2x.png"),
    (128, 1, "icon_128x128.png"),
    (128, 2, "icon_128x128@2x.png"),
    (256, 1, "icon_256x256.png"),
    (256, 2, "icon_256x256@2x.png"),
    (512, 1, "icon_512x512.png"),
    (512, 2, "icon_512x512@2x.png"),
]


def render_svg_to_png(svg_path: Path, png_path: Path, size_px: int) -> None:
    with open(svg_path, "rb") as f:
        svg_bytes = QByteArray(f.read())
    renderer = QSvgRenderer(svg_bytes)
    if not renderer.isValid():
        raise RuntimeError(f"SVG 가 유효하지 않습니다: {svg_path}")

    image = QImage(QSize(size_px, size_px), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    renderer.render(painter)
    painter.end()
    image.save(str(png_path), "PNG")


def main():
    design_dir = Path(__file__).resolve().parent
    svg_path = design_dir / "icon.svg"
    iconset_dir = design_dir / "icon.iconset"
    icns_path = design_dir / "icon.icns"

    if not svg_path.exists():
        print(f"[ERR] {svg_path} 가 없습니다.", file=sys.stderr)
        sys.exit(1)

    if iconset_dir.exists():
        shutil.rmtree(iconset_dir)
    iconset_dir.mkdir()
    if icns_path.exists():
        icns_path.unlink()

    print(f"[1/3] PNG 렌더링 ({len(ICONSET_SIZES)}개 사이즈)")
    for base, scale, fname in ICONSET_SIZES:
        actual_px = base * scale
        out_png = iconset_dir / fname
        render_svg_to_png(svg_path, out_png, actual_px)
        print(f"      {fname}  ({actual_px}×{actual_px})")

    print("[2/3] iconutil 로 .icns 패키지 생성")
    try:
        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset_dir), "-o", str(icns_path)],
            check=True,
        )
    except FileNotFoundError:
        print("[ERR] iconutil 명령을 찾을 수 없습니다. macOS 에서 실행해야 합니다.",
              file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"[ERR] iconutil 실패: {e}", file=sys.stderr)
        sys.exit(1)

    shutil.rmtree(iconset_dir, ignore_errors=True)

    print(f"[3/3] 완료: {icns_path}")


if __name__ == "__main__":
    main()
