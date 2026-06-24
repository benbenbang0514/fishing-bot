"""Interactive HSV color calibration tool with live mask preview."""

import cv2
import numpy as np
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from capture import ScreenCapture
from config import load_config, save_config, update_hsv

WINDOW_NAME = "HSV Calibrator - Green/Yellow"
TRACKBAR_WINDOW = "Controls"


def nothing(x):
    pass


def run_calibrator():
    cfg = load_config()
    if not cfg.has_roi():
        print("No ROI configured. Run main.py first to select a region, or set ROI manually in config.json.")
        return

    roi = cfg.roi.rect

    cv2.namedWindow(WINDOW_NAME)
    cv2.namedWindow(TRACKBAR_WINDOW)
    cv2.resizeWindow(TRACKBAR_WINDOW, 500, 400)

    current_color = "green"

    cv2.createTrackbar("H Min", TRACKBAR_WINDOW, cfg.hsv_green.h_min, 179, nothing)
    cv2.createTrackbar("H Max", TRACKBAR_WINDOW, cfg.hsv_green.h_max, 179, nothing)
    cv2.createTrackbar("S Min", TRACKBAR_WINDOW, cfg.hsv_green.s_min, 255, nothing)
    cv2.createTrackbar("V Min", TRACKBAR_WINDOW, cfg.hsv_green.v_min, 255, nothing)

    def load_trackbar_values(color_name):
        hsv = getattr(cfg, f"hsv_{color_name}")
        cv2.setTrackbarPos("H Min", TRACKBAR_WINDOW, hsv.h_min)
        cv2.setTrackbarPos("H Max", TRACKBAR_WINDOW, hsv.h_max)
        cv2.setTrackbarPos("S Min", TRACKBAR_WINDOW, hsv.s_min)
        cv2.setTrackbarPos("V Min", TRACKBAR_WINDOW, hsv.v_min)

    cap = ScreenCapture(roi)

    print("=" * 50)
    print("HSV Calibration Tool")
    print("=" * 50)
    print("Press 'G' to calibrate GREEN (target zone)")
    print("Press 'Y' to calibrate YELLOW (player cursor)")
    print("Press 'S' to SAVE current values to config.json")
    print("Press 'ESC' to exit")
    print("=" * 50)

    while True:
        frame = cap.grab()
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        h_min = cv2.getTrackbarPos("H Min", TRACKBAR_WINDOW)
        h_max = cv2.getTrackbarPos("H Max", TRACKBAR_WINDOW)
        s_min = cv2.getTrackbarPos("S Min", TRACKBAR_WINDOW)
        v_min = cv2.getTrackbarPos("V Min", TRACKBAR_WINDOW)

        lower = np.array([h_min, s_min, v_min], dtype=np.uint8)
        upper = np.array([h_max, 255, 255], dtype=np.uint8)
        mask = cv2.inRange(hsv, lower, upper)

        kernel = np.ones((3, 3), np.uint8)
        mask_clean = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(mask_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        debug = frame.copy()
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            area = w * h
            if area > 20:
                color = (0, 255, 0) if current_color == "green" else (0, 255, 255)
                cv2.rectangle(debug, (x, y), (x + w, y + h), color, 2)

        mask_display = cv2.cvtColor(mask_clean, cv2.COLOR_GRAY2BGR)

        combined_top = np.hstack([debug, mask_display])

        info_text = f"Calibrating: {current_color.upper()} | Press G/Y to switch | S to save | ESC to quit"
        cv2.putText(combined_top, info_text, (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        cv2.imshow(WINDOW_NAME, combined_top)

        key = cv2.waitKey(1) & 0xFF

        if key == ord("g"):
            current_color = "green"
            load_trackbar_values("green")
            print("[*] Switched to GREEN calibration")
        elif key == ord("y"):
            current_color = "yellow"
            load_trackbar_values("yellow")
            print("[*] Switched to YELLOW calibration")
        elif key == ord("s"):
            update_hsv(cfg, current_color, {
                "h_min": h_min, "h_max": h_max,
                "s_min": s_min, "v_min": v_min,
            })
            print(f"[✓] Saved {current_color} HSV values to config.json")
        elif key == 27:
            break

    cap.close()
    cv2.destroyAllWindows()
    print("Calibration complete.")


if __name__ == "__main__":
    run_calibrator()
