"""Build prep: pre-generate the comtypes UI Automation bindings and write build/geyser.ico.

Pre-generating means the frozen exe imports comtypes.gen.UIAutomationClient instead of
generating Python code from the type library at runtime.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import comtypes.client  # noqa: E402

comtypes.client.GetModule("UIAutomationCore.dll")
from comtypes.gen import UIAutomationClient  # noqa: E402

print(f"{UIAutomationClient.__name__} bindings ready")

from io import BytesIO  # noqa: E402

from PIL import Image  # noqa: E402
from PySide6.QtCore import QBuffer, QIODevice  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from geyser.ui.plume import ICON_SIZES, render_icon_image  # noqa: E402

app = QGuiApplication(sys.argv)


def to_pil(size):
    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    render_icon_image(size).save(buf, "PNG")
    return Image.open(BytesIO(bytes(buf.data()))).convert("RGBA")


out = ROOT / "build"
out.mkdir(exist_ok=True)
images = [to_pil(size) for size in ICON_SIZES]
# Each size is drawn separately so the small tray sizes stay crisp instead of being downscaled.
images[-1].save(out / "geyser.ico", sizes=[(s, s) for s in ICON_SIZES], append_images=images[:-1])
print(f"wrote {out / 'geyser.ico'}")
