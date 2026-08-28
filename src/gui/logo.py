"""Logo asset loading for MediTrack GUI."""

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QImage

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
LOGO_PATH = _PROJECT_ROOT / "assets" / "logo.png"


def load_logo_pixmap(path: Path = LOGO_PATH, width: int = 200) -> QPixmap:
    """Load logo and strip near-white pixels for dark backgrounds."""
    if not path.exists():
        return QPixmap()
    image = QImage(str(path))
    if image.isNull():
        return QPixmap()
    image = image.convertToFormat(QImage.Format.Format_ARGB32)
    for y in range(image.height()):
        for x in range(image.width()):
            color = image.pixelColor(x, y)
            if color.red() > 230 and color.green() > 230 and color.blue() > 230:
                color.setAlpha(0)
                image.setPixelColor(x, y, color)
    pixmap = QPixmap.fromImage(image)
    if pixmap.isNull():
        return QPixmap()
    return pixmap.scaledToWidth(width, Qt.TransformationMode.SmoothTransformation)
