from __future__ import annotations

import cv2
import numpy as np
import qrcode


def make_qr_bgr(text: str, box_size: int = 10, border: int = 2) -> np.ndarray:
    """Create an OpenCV BGR QR image for the supplied connection URL."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(text)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    rgb = np.array(image)
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
