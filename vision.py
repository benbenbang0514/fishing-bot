"""Computer vision pipeline: anchor detection and bar state extraction."""

import cv2
import numpy as np
from typing import Optional, Tuple, NamedTuple, List
import time
import re
import os

try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False


class BarState(NamedTuple):
    green_x: float
    green_w: float
    yellow_x: float


class VisionPipeline:
    def __init__(self, hsv_green_lower, hsv_green_upper, hsv_yellow_lower, hsv_yellow_upper,
                 assumed_green_w: Optional[float] = None):
        self.hsv_green_lower = np.array(hsv_green_lower, dtype=np.uint8)
        self.hsv_green_upper = np.array(hsv_green_upper, dtype=np.uint8)
        self.hsv_yellow_lower = np.array(hsv_yellow_lower, dtype=np.uint8)
        self.hsv_yellow_upper = np.array(hsv_yellow_upper, dtype=np.uint8)

        self._anchor_offset: Optional[int] = None
        self._last_anchor_time: float = 0.0
        self._anchor_interval: float = 2.0
        self._template: Optional[np.ndarray] = None
        self._missing_frames: int = 0
        self._debug_green_count: int = 0
        self._debug_yellow_count: int = 0
        self.assumed_green_w = assumed_green_w
        self._debug_green_rect: Optional[Tuple[int, int, int, int]] = None
        self._debug_yellow_rect: Optional[Tuple[int, int, int, int]] = None
        self._last_green_rect: Optional[Tuple[int, int, int, int]] = None
        self._last_yellow_x: Optional[float] = None
        self._last_yellow_time: float = 0.0
        self._debug_green_candidates = []
        self._debug_yellow_candidates = []

    def load_template(self, path: str) -> bool:
        tmpl = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if tmpl is None:
            return False
        self._template = tmpl
        return True

    def detect_difficulty(self, frame: np.ndarray, difficulties: List[int], field2_roi=None) -> Optional[int]:
        if not HAS_TESSERACT:
            return None
        h, w = frame.shape[:2]
        
        if field2_roi is not None and field2_roi.valid:
            fx, fy, fw, fh = field2_roi.rect
            crop = frame[fy:fy+fh, fx:fx+fw]
            source_name = "field2"
        else:
            left_crop = frame[:, :max(1, int(w * 0.22))]
            crop = left_crop
            source_name = "left_crop"
        
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        kernel = np.ones((2, 2), np.uint8)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        timestamp = int(time.time() * 1000)
        bot_dir = os.path.dirname(os.path.abspath(__file__))
        ocr_debug_dir = os.path.join(bot_dir, "ocr_debug")
        os.makedirs(ocr_debug_dir, exist_ok=True)
        
        original_path = os.path.join(ocr_debug_dir, f"original_{timestamp}.png")
        thresh_path = os.path.join(ocr_debug_dir, f"thresh_{timestamp}.png")
        log_path = os.path.join(ocr_debug_dir, "ocr_log.txt")
        
        cv2.imwrite(original_path, crop)
        cv2.imwrite(thresh_path, thresh)
        
        text = pytesseract.image_to_string(thresh, config='--psm 6 -c tessedit_char_whitelist=0123456789')
        
        log_entry = (
            f"[{timestamp}] Source: {source_name}\n"
            f"  Raw text: '{text.strip()}'\n"
            f"  Original: {original_path}\n"
            f"  Threshold: {thresh_path}\n"
        )
        
        # Check if any difficulty number appears in the raw text
        found = None
        for d in difficulties:
            if str(d) in text.strip():
                found = d
                break
        
        if found is not None:
            log_entry += f"  Result: Matched difficulty {found}\n\n"
            with open(log_path, "a") as f:
                f.write(log_entry)
            print(f"[OCR] Matched difficulty: {found}. Log: {log_path}")
            return found
        
        digits = re.findall(r'\d+', text)
        if not digits:
            log_entry += f"  Result: No digits found\n\n"
            with open(log_path, "a") as f:
                f.write(log_entry)
            print(f"[OCR] No digits found in text. Log: {log_path}")
            return None
        
        log_entry += f"  Extracted digits: {digits}\n"
        # Check if any difficulty matches part of a digit string
        # Allow repeats (e.g., '66' for '6/6', '1212' for '12/12')
        found = None
        for d in difficulties:
            d_str = str(d)
            for digit_str in digits:
                # Match if the difficulty is repeated (e.g., '66' for '6/6', '1212' for '12/12')
                if digit_str == d_str * (len(digit_str) // len(d_str)) and len(digit_str) % len(d_str) == 0:
                    found = d
                    break
                # Or exact match
                elif digit_str == d_str:
                    found = d
                    break
            if found is not None:
                break
        
        if found is not None:
            log_entry += f"  Result: Matched difficulty {found} (substring match)\n\n"
            with open(log_path, "a") as f:
                f.write(log_entry)
            print(f"[OCR] Matched difficulty: {found} (substring). Log: {log_path}")
            return found
        
        log_entry += f"  Result: No match in difficulties {difficulties}\n\n"
        with open(log_path, "a") as f:
            f.write(log_entry)
        print(f"[OCR] No match. Log: {log_path}")
        return None

    def detect_chinese_text(self, frame: np.ndarray, target_text: str = "點擊空白區域") -> bool:
        timestamp = int(time.time() * 1000)
        bot_dir = os.path.dirname(os.path.abspath(__file__))
        ocr_debug_dir = os.path.join(bot_dir, "ocr_debug")
        os.makedirs(ocr_debug_dir, exist_ok=True)

        original_path = os.path.join(ocr_debug_dir, f"field3_original_{timestamp}.png")
        thresh_path = os.path.join(ocr_debug_dir, f"field3_thresh_{timestamp}.png")
        log_path = os.path.join(ocr_debug_dir, "ocr_log.txt")

        if not HAS_TESSERACT:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(
                    f"[{timestamp}] Source: field3\n"
                    f"  Target text: '{target_text}'\n"
                    f"  Result: pytesseract not available\n\n"
                )
            return False
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        _, thresh_inv = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        kernel = np.ones((2, 2), np.uint8)
        thresh_inv = cv2.morphologyEx(thresh_inv, cv2.MORPH_CLOSE, kernel)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

        cv2.imwrite(original_path, frame)
        cv2.imwrite(thresh_path, thresh_inv)
        
        try:
            ocr_inputs = (
                ("gray", gray),
                ("thresh_inv", thresh_inv),
                ("thresh", thresh),
            )
            ocr_results = []
            for source_name, image in ocr_inputs:
                for psm in (6, 7, 11):
                    text = pytesseract.image_to_string(image, config=f'--psm {psm} -l chi_tra+eng')
                    ocr_results.append((source_name, psm, text.strip()))
            text = "\n".join(result for _, _, result in ocr_results if result)
            raw_text = text.strip()
            normalized_text = re.sub(r"\s+", "", raw_text)
            matched = (
                target_text in raw_text
                or target_text in normalized_text
                or sum(1 for char in target_text if char in normalized_text) >= 4
            )
            ocr_details = "\n".join(
                f"    {source_name} psm={psm}: '{result}'"
                for source_name, psm, result in ocr_results
            )
            log_entry = (
                f"[{timestamp}] Source: field3\n"
                f"  Target text: '{target_text}'\n"
                f"  Raw text: '{raw_text}'\n"
                f"  Normalized text: '{normalized_text}'\n"
                f"  OCR attempts:\n{ocr_details}\n"
                f"  Original: {original_path}\n"
                f"  Threshold: {thresh_path}\n"
                f"  Result: {'Matched target text' if matched else 'No target text match'}\n\n"
            )
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(log_entry)
            print(f"[OCR FIELD3] {'Matched' if matched else 'No match'}. Log: {log_path}")
            return matched
        except Exception as e:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(
                    f"[{timestamp}] Source: field3\n"
                    f"  Target text: '{target_text}'\n"
                    f"  Original: {original_path}\n"
                    f"  Threshold: {thresh_path}\n"
                    f"  Result: OCR error: {e}\n\n"
                )
            print(f"[OCR FIELD3] Error: {e}. Log: {log_path}")
            return False

    def update_hsv(self, color: str, lower, upper):
        arr_lower = np.array(lower, dtype=np.uint8)
        arr_upper = np.array(upper, dtype=np.uint8)
        if color == "green":
            self.hsv_green_upper = arr_upper
        elif color == "yellow":
            self.hsv_yellow_lower = arr_lower
            self.hsv_yellow_upper = arr_upper

    def find_anchor(self, frame: np.ndarray, force: bool = False) -> int:
        now = time.perf_counter()
        if not force and self._anchor_offset is not None:
            if now - self._last_anchor_time < self._anchor_interval:
                return self._anchor_offset

        if self._template is not None:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            result = cv2.matchTemplate(gray, self._template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if max_val >= 0.85:
                self._anchor_offset = max_loc[0]
                self._last_anchor_time = now
                return self._anchor_offset

        offset = self._detect_anchor_fallback(frame)
        self._anchor_offset = offset
        self._last_anchor_time = now
        return offset

    def _detect_anchor_fallback(self, frame: np.ndarray) -> int:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return 0
        largest = max(contours, key=cv2.contourArea)
        x, _, w, _ = cv2.boundingRect(largest)
        if w > frame.shape[1] * 0.3:
            return x
        return 0

    def extract_state(self, frame: np.ndarray, anchor_offset: int = 0) -> Optional[BarState]:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        green_mask = cv2.inRange(hsv, self.hsv_green_lower, self.hsv_green_upper)
        yellow_mask = cv2.inRange(hsv, self.hsv_yellow_lower, self.hsv_yellow_upper)

        kernel = np.ones((3, 3), np.uint8)
        green_close_kernel = np.ones((9, 3), np.uint8)
        green_mask = cv2.morphologyEx(green_mask, cv2.MORPH_OPEN, kernel)
        green_mask = cv2.morphologyEx(green_mask, cv2.MORPH_CLOSE, green_close_kernel)
        yellow_mask = cv2.morphologyEx(yellow_mask, cv2.MORPH_OPEN, kernel)

        green_contours, _ = cv2.findContours(green_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        yellow_contours, _ = cv2.findContours(yellow_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        self._debug_green_count = len(green_contours)
        self._debug_yellow_count = len(yellow_contours)

        green_rect = self._best_green_contour(green_contours, frame.shape)
        yellow_rect = self._best_yellow_contour(yellow_contours, frame.shape, green_rect)
        self._debug_green_rect = green_rect
        self._debug_yellow_rect = yellow_rect

        if green_rect is None or yellow_rect is None:
            self._missing_frames += 1
            return None

        self._missing_frames = 0
        self._last_green_rect = green_rect

        gx, _, gw, _ = green_rect
        if self.assumed_green_w is not None:
            gw = max(float(gw), float(self.assumed_green_w))
        yx, _, yw, _ = yellow_rect
        yellow_x = float(yx + yw / 2.0)
        now = time.perf_counter()

        if self._last_yellow_x is not None:
            dt = max(now - self._last_yellow_time, 0.001)
            max_jump = max(180.0, frame.shape[1] * 0.18, 1800.0 * dt)
            if abs(yellow_x - self._last_yellow_x) > max_jump:
                self._debug_yellow_rect = None
                self._missing_frames += 1
                return None

        self._last_yellow_x = yellow_x
        self._last_yellow_time = now

        return BarState(
            green_x=float(gx),
            green_w=float(gw),
            yellow_x=yellow_x,
        )

    def _best_green_contour(self, contours, shape) -> Optional[Tuple[int, int, int, int]]:
        valid = []
        h, w = shape[:2]
        for c in contours:
            x, y, cw, ch = cv2.boundingRect(c)
            area = cw * ch
            if area < 30:
                continue
            aspect = cw / max(ch, 1)
            if aspect < 4.0:
                continue
            if cw < 25:
                continue
            if ch < 3 or ch > max(24, h * 0.2):
                continue
            if y < h * 0.12 or y > h * 0.62:
                continue
            valid.append((x, y, cw, ch, area))
        self._debug_green_candidates = valid

        if not valid:
            return None

        merged = []
        for rect in sorted(valid, key=lambda r: r[0]):
            x, y, cw, ch, area = rect
            if not merged:
                merged.append([x, y, x + cw, y + ch, area])
                continue
            prev = merged[-1]
            horizontal_gap = x - prev[2]
            vertical_overlap = min(prev[3], y + ch) - max(prev[1], y)
            if horizontal_gap <= 40 and vertical_overlap > 0:
                prev[1] = min(prev[1], y)
                prev[2] = max(prev[2], x + cw)
                prev[3] = max(prev[3], y + ch)
                prev[4] += area
            else:
                merged.append([x, y, x + cw, y + ch, area])
        valid = [(x1, y1, x2 - x1, y2 - y1, area) for x1, y1, x2, y2, area in merged]

        track_center_y = h * 0.35
        if self._last_green_rect is not None:
            last_x = self._last_green_rect[0]
            nearby = [r for r in valid if abs(r[0] - last_x) <= max(120, w * 0.12)]
            if nearby:
                valid = nearby
        valid.sort(key=lambda r: (
            abs(r[0] - self._last_green_rect[0]) if self._last_green_rect is not None else 0,
            abs((r[1] + r[3] / 2) - track_center_y),
            -r[4],
        ))
        x, y, cw, ch, _ = valid[0]
        return (x, y, cw, ch)

    def _best_yellow_contour(self, contours, shape, green_rect=None) -> Optional[Tuple[int, int, int, int]]:
        valid = []
        h, w = shape[:2]
        for c in contours:
            x, y, cw, ch = cv2.boundingRect(c)
            area = cw * ch
            if area < 8:
                continue
            if cw > max(16, w * 0.03):
                continue
            if ch < 8:
                continue
            if ch / max(cw, 1) < 1.8:
                continue
            if y < h * 0.15 or y > h * 0.7:
                continue
            if green_rect is not None:
                _, gy, _, gh = green_rect
                if abs((y + ch / 2) - (gy + gh / 2)) > max(28, gh * 3):
                    continue
            valid.append((x, y, cw, ch, area))
        self._debug_yellow_candidates = valid

        if not valid:
            return None

        if green_rect is not None:
            gx, _, gw, _ = green_rect
            green_center = gx + gw / 2
            search_radius = max(260, gw * 3.0)
            nearby = [
                r for r in valid
                if abs((r[0] + r[2] / 2) - green_center) <= search_radius
            ]
            if nearby:
                valid = nearby
            else:
                valid.sort(key=lambda r: r[4], reverse=True)
        if self._last_yellow_x is not None:
            stable = [
                r for r in valid
                if abs((r[0] + r[2] / 2) - self._last_yellow_x) <= max(220, w * 0.12)
            ]
            if stable:
                valid = stable
                valid.sort(key=lambda r: (
                    abs((r[0] + r[2] / 2) - self._last_yellow_x),
                    -r[4],
                ))
            elif green_rect is not None:
                valid.sort(key=lambda r: (
                    abs((r[0] + r[2] / 2) - green_center),
                    -r[4],
                ))
            else:
                valid.sort(key=lambda r: r[4], reverse=True)
        elif green_rect is not None:
            valid.sort(key=lambda r: (
                abs((r[0] + r[2] / 2) - green_center),
                -r[4],
            ))
        else:
            valid.sort(key=lambda r: r[4], reverse=True)
        x, y, cw, ch, _ = valid[0]
        return (x, y, cw, ch)

    @property
    def debug_green_count(self) -> int:
        return self._debug_green_count

    @property
    def debug_yellow_count(self) -> int:
        return self._debug_yellow_count

    @property
    def debug_green_rect(self) -> Optional[Tuple[int, int, int, int]]:
        return self._debug_green_rect

    @property
    def debug_yellow_rect(self) -> Optional[Tuple[int, int, int, int]]:
        return self._debug_yellow_rect

    @property
    def debug_green_candidates(self):
        return self._debug_green_candidates

    @property
    def debug_yellow_candidates(self):
        return self._debug_yellow_candidates

    @property
    def missing_frame_count(self) -> int:
        return self._missing_frames

    def draw_debug(self, frame: np.ndarray, state: Optional[BarState]) -> np.ndarray:
        debug = frame.copy()
        if self._debug_green_rect is not None:
            x, y, w, h = self._debug_green_rect
            cv2.rectangle(debug, (x, y), (x + w, y + h), (0, 180, 0), 1)
        if self._debug_yellow_rect is not None:
            x, y, w, h = self._debug_yellow_rect
            cv2.rectangle(debug, (x, y), (x + w, y + h), (0, 180, 180), 1)
        if state is not None:
            cv2.rectangle(
                debug,
                (int(state.green_x), 0),
                (int(state.green_x + state.green_w), debug.shape[0]),
                (0, 255, 0), 2,
            )
            cv2.rectangle(
                debug,
                (int(state.yellow_x - 5), 0),
                (int(state.yellow_x + 5), debug.shape[0]),
                (0, 255, 255), 2,
            )
        return debug
