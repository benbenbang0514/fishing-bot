"""Screen capture wrapper using mss for fast cross-platform capture."""

import numpy as np
from typing import Optional, Tuple
import mss


class ScreenCapture:
    def __init__(self, roi: Optional[Tuple[int, int, int, int]] = None):
        self._sct = mss.mss()
        self._monitor: Optional[dict] = None
        if roi:
            self.set_roi(roi)

    def set_roi(self, roi: Tuple[int, int, int, int]) -> None:
        x, y, w, h = roi
        self._monitor = {
            "left": x,
            "top": y,
            "width": w,
            "height": h,
        }

    def grab(self, roi: Optional[Tuple[int, int, int, int]] = None) -> np.ndarray:
        if roi:
            x, y, w, h = roi
            monitor = {"left": x, "top": y, "width": w, "height": h}
        elif self._monitor:
            monitor = self._monitor
        else:
            raise RuntimeError("No ROI set for capture")

        img = self._sct.grab(monitor)
        frame = np.array(img, dtype=np.uint8)
        frame = frame[:, :, :3]
        return frame

    def close(self) -> None:
        if self._sct:
            self._sct.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
