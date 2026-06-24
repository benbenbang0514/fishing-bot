"""Auto-Fishing Bot - Entry point. Calibration → main loop."""

import argparse
import ctypes
import os
import sys
import time
import tkinter as tk
from tkinter import ttk

import cv2
import numpy as np

from config import load_config, save_config, ROIConfig
from capture import ScreenCapture
from vision import VisionPipeline, BarState
from controller import InputController
from selector import run_overlay_selector
from input_log import clear_logs, write_read_log

TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "anchor_template.png")
DETECTION_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "detection_log.txt")
VK_CODES = {
    "a": 0x41,
    "d": 0x44,
}


def write_detection_log(message: str) -> None:
    stamp = time.strftime("%H:%M:%S")
    with open(DETECTION_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{stamp}] {message}\n")


def select_roi(prompt: str) -> ROIConfig | None:
    result = run_overlay_selector(prompt)
    if result is None:
        return None
    return ROIConfig(x=result[0], y=result[1], w=result[2], h=result[3])


def run_test_mode() -> None:
    cfg = load_config()
    open(DETECTION_LOG_PATH, "w", encoding="utf-8").close()

    print("[TEST] Select FIELD 1: current fishing bar read area.")
    field1 = select_roi("FIELD 1: drag over the fishing bar / current read area")
    if field1 is None:
        print("[TEST] Field 1 selection cancelled.")
        return
    cfg.field1 = field1
    cfg.roi = field1
    save_config(cfg)
    print(f"[TEST] Field 1 saved: {field1.rect}")

    print("[TEST] Select FIELD 2: future second job read area.")
    field2 = select_roi("FIELD 2: drag over second read area for later use")
    if field2 is not None:
        cfg.field2 = field2
        save_config(cfg)
        print(f"[TEST] Field 2 saved: {field2.rect}")
    else:
        print("[TEST] Field 2 skipped.")

    assumed_green_w = cfg.difficulty_lengths.get(str(cfg.difficulty))
    vision = VisionPipeline(
        cfg.hsv_green.lower,
        cfg.hsv_green.upper,
        cfg.hsv_yellow.lower,
        cfg.hsv_yellow.upper,
        assumed_green_w,
    )

    print("[TEST] Showing live Field 1 preview. Press ESC in the preview window to stop.")
    cv2.namedWindow("Field 1 Test Preview - ESC to close", cv2.WINDOW_NORMAL)
    cv2.setWindowProperty("Field 1 Test Preview - ESC to close", cv2.WND_PROP_TOPMOST, 1)
    last_log = 0.0
    consecutive_empty_logs = 0
    with ScreenCapture(field1.rect) as capture:
        while True:
            frame = capture.grab()
            state = vision.extract_state(frame)
            debug = vision.draw_debug(frame, state)
            text = "NO DETECTION"
            if state is not None:
                text = f"D={cfg.difficulty} | G start={state.green_x:.0f} w={state.green_w:.0f} | Y x={state.yellow_x:.0f}"
            now = time.perf_counter()
            if now - last_log >= 0.5:
                is_empty = (
                    state is None
                    and vision.debug_green_count == 0
                    and vision.debug_yellow_count == 0
                )
                if is_empty:
                    consecutive_empty_logs += 1
                else:
                    consecutive_empty_logs = 0
                log_line = (
                    f"TEST state={state} green_rect={vision.debug_green_rect} "
                    f"yellow_rect={vision.debug_yellow_rect} "
                    f"green_candidates={vision.debug_green_candidates} "
                    f"yellow_candidates={vision.debug_yellow_candidates} "
                    f"contours G={vision.debug_green_count} Y={vision.debug_yellow_count}"
                )
                if consecutive_empty_logs <= 3:
                    print(f"[TEST READ] {log_line}")
                    write_detection_log(log_line)
                last_log = now
            cv2.putText(debug, text, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.imshow("Field 1 Test Preview - ESC to close", debug)
            if cv2.waitKey(1) & 0xFF == 27:
                break
    cv2.destroyAllWindows()


def run_input_test_mode() -> None:
    clear_logs()
    root = tk.Tk()
    root.title("Fishing Bot Input Test")
    root.geometry("420x140+200+200")
    label = ttk.Label(root, text="Input test field. The bot will type A then D.")
    label.pack(pady=(12, 6))
    entry = ttk.Entry(root, width=40)
    entry.pack(pady=6)
    status = ttk.Label(root, text="Starting...")
    status.pack(pady=6)
    controller = InputController()

    def start_test():
        entry.focus_force()
        root.after(300, lambda: controller._key_down("a"))
        root.after(450, lambda: controller._key_up("a"))
        root.after(700, lambda: controller._key_down("d"))
        root.after(850, lambda: controller._key_up("d"))
        root.after(1100, finish_test)

    def finish_test():
        value = entry.get()
        status.config(text=f"Text field read: {value!r}")
        write_read_log(f"[INPUT TEST] text_field_read={value!r}")
        controller.release_all()

    root.after(500, start_test)
    root.mainloop()


class DebugOverlay:
    def __init__(self, on_change_field1=None, on_change_field2=None, on_start=None, on_stop=None):
        self.root = tk.Tk()
        self.root.title("Fishing Bot")
        self.root.attributes("-topmost", True)
        self.root.geometry("420x660+100+100")
        self.root.configure(bg="#1a1a2e")
        self.root.protocol("WM_DELETE_WINDOW", lambda: self._on_close())
        self._make_non_activating()
        self._running = True
        self._on_change_field1 = on_change_field1
        self._on_change_field2 = on_change_field2
        self._on_start = on_start
        self._on_stop = on_stop
        self._show_field2 = False

        style = ttk.Style()
        style.configure("Dark.TLabel", background="#1a1a2e", foreground="#e0e0e0")
        style.configure("Key.TLabel", background="#1a1a2e", foreground="#00ff88", font=("Consolas", 28, "bold"))
        style.configure("Header.TLabel", background="#1a1a2e", foreground="#8888cc", font=("Consolas", 10))

        header = ttk.Label(self.root, text="FISHING BOT", style="Header.TLabel")
        header.pack(pady=(8, 2))

        self._key_label = ttk.Label(self.root, text="-", style="Key.TLabel")
        self._key_label.pack(pady=2)

        self._fps_label = ttk.Label(self.root, text="FPS: --", style="Dark.TLabel", font=("Consolas", 11))
        self._fps_label.pack(pady=1)

        sep1 = ttk.Separator(self.root, orient="horizontal")
        sep1.pack(fill="x", padx=15, pady=4)

        self._green_label = ttk.Label(self.root, text="Green:  x=---  w=---", style="Dark.TLabel", font=("Consolas", 11))
        self._green_label.pack(pady=1)

        self._yellow_label = ttk.Label(self.root, text="Yellow: x=---", style="Dark.TLabel", font=("Consolas", 11))
        self._yellow_label.pack(pady=1)

        self._output_label = ttk.Label(self.root, text="Output: ---", style="Dark.TLabel", font=("Consolas", 11))
        self._output_label.pack(pady=1)

        self._contour_label = ttk.Label(self.root, text="Cnt: G=? Y=?", style="Dark.TLabel", font=("Consolas", 10))
        self._contour_label.pack(pady=1)

        self._difficulty_label = ttk.Label(self.root, text="Difficulty: ---", style="Dark.TLabel", font=("Consolas", 11))
        self._difficulty_label.pack(pady=1)

        sep2 = ttk.Separator(self.root, orient="horizontal")
        sep2.pack(fill="x", padx=15, pady=4)

        self._canvas = tk.Canvas(self.root, width=390, height=200, bg="black", highlightthickness=1,
                                 highlightbackground="#444466")
        self._canvas.pack(pady=6)

        button_frame = tk.Frame(self.root, bg="#1a1a2e")
        button_frame.pack(pady=4)
        
        self._field1_btn = tk.Button(button_frame, text="Change Field 1", command=self._change_field1,
                                     bg="#2a2a4e", fg="#e0e0e0", font=("Consolas", 9), width=14)
        self._field1_btn.pack(side="left", padx=3)
        
        self._field2_btn = tk.Button(button_frame, text="Change Field 2", command=self._change_field2,
                                     bg="#2a2a4e", fg="#e0e0e0", font=("Consolas", 9), width=14)
        self._field2_btn.pack(side="left", padx=3)

        control_frame = tk.Frame(self.root, bg="#1a1a2e")
        control_frame.pack(pady=4)

        self._start_btn = tk.Button(control_frame, text="Start", command=self._start,
                                    bg="#1f6f3f", fg="#ffffff", font=("Consolas", 10, "bold"), width=14)
        self._start_btn.pack(side="left", padx=4)

        self._stop_btn = tk.Button(control_frame, text="Stop", command=self._stop,
                                   bg="#8a2a2a", fg="#ffffff", font=("Consolas", 10, "bold"), width=14)
        self._stop_btn.pack(side="left", padx=4)

        toggle_frame = tk.Frame(self.root, bg="#1a1a2e")
        toggle_frame.pack(pady=2)
        
        self._toggle_btn = tk.Button(toggle_frame, text="Show Field 2", command=self._toggle_field,
                                     bg="#3a3a5e", fg="#e0e0e0", font=("Consolas", 9), width=20)
        self._toggle_btn.pack()

        self._status = ttk.Label(self.root, text="RUNNING", font=("Consolas", 12, "bold"),
                                 foreground="#00ff88", background="#1a1a2e")
        self._status.pack(pady=4)

    def update(self, fps: float, output: float, velocity: float, state, current_key: str,
               green_cnt: int = 0, yellow_cnt: int = 0, debug_frame=None, difficulty: Optional[int] = None,
               field2_frame=None, field3_frame=None):
        if not self._running:
            return
        try:
            self._fps_label.config(text=f"FPS: {fps:.1f}")
            self._output_label.config(text=f"Output: {output:+.2f}")
            self._contour_label.config(text=f"Cnt: G={green_cnt} Y={yellow_cnt}")
            self._difficulty_label.config(text=f"Difficulty: {difficulty if difficulty is not None else '---'}")

            if current_key == "-":
                self._key_label.config(text="·", foreground="#666688")
            else:
                self._key_label.config(text=current_key, foreground="#00ff88")

            if state:
                self._green_label.config(
                    text=f"Green:  x={state.green_x:.0f}  w={state.green_w:.0f}"
                )
                self._yellow_label.config(
                    text=f"Yellow: x={state.yellow_x:.0f}"
                )
                self._status.config(text="TRACKING", foreground="#00ff88")
            else:
                self._green_label.config(text="Green:  x=---  w=---")
                self._yellow_label.config(text="Yellow: x=---")
                self._status.config(text="SEARCHING", foreground="orange")

            if self._show_field2 and field2_frame is not None:
                frame_to_show = field2_frame
            else:
                frame_to_show = debug_frame
            if frame_to_show is not None:
                self._draw_frame(frame_to_show)
        except tk.TclError:
            self._running = False

    def _draw_frame(self, frame):
        h, w = frame.shape[:2]
        scale = min(388 / w, 198 / h)
        new_w, new_h = int(w * scale), int(h * scale)
        resized = cv2.resize(frame, (new_w, new_h))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

        from PIL import Image, ImageTk
        img = Image.fromarray(rgb)
        self._tk_img = ImageTk.PhotoImage(img)
        self._canvas.delete("all")
        self._canvas.create_image(195, 100, image=self._tk_img, anchor="center")

    def set_running(self, running: bool):
        self._running = running
        try:
            self._status.config(text="RUNNING" if running else "STOPPED",
                                foreground="#00ff88" if running else "red")
        except tk.TclError:
            pass

    def _on_close(self):
        self._running = False

    def _change_field1(self):
        if self._on_change_field1:
            self._on_change_field1()

    def _change_field2(self):
        if self._on_change_field2:
            self._on_change_field2()

    def _toggle_field(self):
        self._show_field2 = not self._show_field2
        self._toggle_btn.config(text="Show Field 1" if self._show_field2 else "Show Field 2")

    def _start(self):
        if self._on_start:
            self._on_start()

    def _stop(self):
        if self._on_stop:
            self._on_stop()

    def process_events(self):
        if self._running:
            try:
                self.root.update()
            except tk.TclError:
                self._running = False

    def _make_non_activating(self):
        if sys.platform != "win32":
            return
        try:
            self.root.update_idletasks()
            hwnd = self.root.winfo_id()
            user32 = ctypes.windll.user32
            gwl_exstyle = -20
            ws_ex_noactivate = 0x08000000
            ws_ex_toolwindow = 0x00000080
            get_window_long = user32.GetWindowLongW
            set_window_long = user32.SetWindowLongW
            style = get_window_long(hwnd, gwl_exstyle)
            set_window_long(hwnd, gwl_exstyle, style | ws_ex_noactivate | ws_ex_toolwindow)
        except tk.TclError:
            pass


class FishingBot:
    def __init__(self):
        self.config = load_config()
        self.capture: ScreenCapture = None
        self.vision: VisionPipeline = None
        self.controller: InputController = None
        self.debug_overlay: DebugOverlay = None
        self._running = False
        self._prev_yellow_x = None
        self._prev_time = None
        self._run_difficulty = None
        self._ocr_warned = False
        self._last_ocr_attempt = 0.0
        self._ocr_attempted = False
        self._consecutive_green = 0
        self._consecutive_green_miss = 0
        self._paused = False
        self._recapture_field2 = False
        self._automation_enabled = True
        self._last_state = None
        
        # Field 3 auto-clicking
        self._field3_state = "idle"
        self._field3_missing_start_time = None
        self._field3_next_action_time = None
        self._field3_last_f_time = None
        self._field3_f_attempts = 0

    def setup(self) -> bool:
        active_roi = self.config.active_roi()
        if active_roi is None or not active_roi.valid:
            print("[!] No Field 1/ROI configured. Launching selection overlay...")
            field1 = select_roi("FIELD 1: drag over the fishing bar / current read area")
            if field1 is None:
                print("[!] ROI selection cancelled. Exiting.")
                return False
            self.config.field1 = field1
            self.config.roi = field1
            save_config(self.config)
            active_roi = field1
            print(f"[✓] Field 1 saved: {active_roi.rect}")

        self.capture = ScreenCapture(active_roi.rect)
        self.capture_field2 = None
        if self.config.field2 is not None and self.config.field2.valid:
            self.capture_field2 = ScreenCapture(self.config.field2.rect)
            print(f"[✓] Field 2 capture initialized: {self.config.field2.rect}")

        self.vision = VisionPipeline(
            self.config.hsv_green.lower,
            self.config.hsv_green.upper,
            self.config.hsv_yellow.lower,
            self.config.hsv_yellow.upper,
            None,
        )

        if os.path.exists(TEMPLATE_PATH):
            self.vision.load_template(TEMPLATE_PATH)
            print("[✓] Anchor template loaded.")
        else:
            print("[!] No anchor_template.png found. Using fallback anchor detection.")
            print("    To improve accuracy, crop the fish icon from a screenshot and save as:")
            print(f"    {TEMPLATE_PATH}")

        self.controller = InputController(
            left_key=self.config.keys.left,
            right_key=self.config.keys.right,
            deadzone_percent=self.config.deadzone_percent,
            kp=self.config.kp,
            input_mode=self.config.input_mode,
        )

        self.debug_overlay = DebugOverlay(
            on_change_field1=self._change_field1,
            on_change_field2=self._change_field2,
            on_start=self._start_automation,
            on_stop=self._stop_automation
        )

        return True

    def run(self):
        if not self.setup():
            return

        self._running = True
        clear_logs()
        print("\n" + "=" * 50)
        print("Fishing Bot RUNNING")
        print(f"Field 1 ROI: {self.config.active_roi().rect}")
        print(f"Keys: A={self.config.keys.left}, D={self.config.keys.right}")
        print(f"Deadzone: {self.config.deadzone_percent*100:.0f}%")
        print(f"Kp: {self.config.kp}")
        print("Difficulty: auto-detect per run")
        print("Press Ctrl+C in terminal to stop.")
        print("=" * 50 + "\n")

        frame_times = []
        fps_display = 0.0
        last_fps_update = time.perf_counter()
        last_read_log = 0.0
        last_input_read_log = 0.0
        consecutive_empty_logs = 0

        try:
            while self._running:
                if self._paused:
                    self.debug_overlay.process_events()
                    time.sleep(0.01)
                    continue
                
                t0 = time.perf_counter()

                frame = self.capture.grab()
                if frame is None or frame.size == 0:
                    time.sleep(0.001)
                    continue
                
                field2_frame = None
                if self.capture_field2 is not None:
                    field2_frame = self.capture_field2.grab()
                
                anchor_offset = self.vision.find_anchor(frame)
                state = self.vision.extract_state(frame, anchor_offset)
                self._last_state = state
                now = time.perf_counter()

                if self._automation_enabled:
                    if state is not None:
                        self._reset_field3_recovery()
                    else:
                        self._handle_field3_recovery(now)

                if now - last_input_read_log >= 1.0:
                    keys = self.controller.read_all_keys()
                    write_read_log(f"keys={keys}")
                    last_input_read_log = now

                if state is None:
                    now = time.perf_counter()
                    if now - last_read_log >= 1.0:
                        is_empty = (
                            self.vision.debug_green_count == 0
                            and self.vision.debug_yellow_count == 0
                        )
                        if is_empty:
                            consecutive_empty_logs += 1
                        else:
                            consecutive_empty_logs = 0
                        log_line = (
                            f"MISS green_rect={self.vision.debug_green_rect} "
                            f"yellow_rect={self.vision.debug_yellow_rect} "
                            f"green_candidates={self.vision.debug_green_candidates} "
                            f"yellow_candidates={self.vision.debug_yellow_candidates} "
                            f"contours G={self.vision.debug_green_count} Y={self.vision.debug_yellow_count}"
                        )
                        if consecutive_empty_logs <= 3:
                            print(f"[READ MISS] {log_line}")
                            write_detection_log(log_line)
                        last_read_log = now
                    if self.vision.missing_frame_count > 10:
                        self.controller.release_all()
                        if self._run_difficulty is not None:
                            print("[RUN] New run detected. Resetting difficulty detection.")
                            self._run_difficulty = None
                    self.debug_overlay.update(
                        fps_display, 0.0, 0.0, None, "-",
                        self.vision.debug_green_count,
                        self.vision.debug_yellow_count,
                        frame,
                        difficulty=self._run_difficulty,
                        field2_frame=field2_frame,
                        field3_frame=None,
                    )
                    self.debug_overlay.process_events()
                    self._cap_fps(t0, self.config.target_fps)
                    continue

                now = time.perf_counter()
                self._detect_run_difficulty(field2_frame, state=state)
                dt = now - self._prev_time if self._prev_time else 0.016
                self._prev_time = now

                output = self.controller.compute(
                    state.green_x, state.green_w, state.yellow_x, dt
                )
                if self._automation_enabled:
                    self.controller.send_input(output)
                else:
                    self.controller.release_all()
                if now - last_read_log >= 1.0:
                    consecutive_empty_logs = 0
                    log_line = (
                        f"OK green_start={state.green_x:.1f} green_w={state.green_w:.1f} "
                        f"yellow_x={state.yellow_x:.1f} key={self.controller.current_key} "
                        f"green_rect={self.vision.debug_green_rect} yellow_rect={self.vision.debug_yellow_rect} "
                        f"green_candidates={self.vision.debug_green_candidates} "
                        f"yellow_candidates={self.vision.debug_yellow_candidates}"
                    )
                    print(f"[READ OK] {log_line}")
                    write_detection_log(log_line)
                    last_read_log = now

                frame_times.append(time.perf_counter() - t0)
                if now - last_fps_update > 0.5:
                    if frame_times:
                        avg_frame_time = sum(frame_times) / len(frame_times)
                        fps_display = 1.0 / avg_frame_time if avg_frame_time > 0 else 0
                    frame_times.clear()
                    last_fps_update = now

                debug_frame = self.vision.draw_debug(frame, state)
                self.debug_overlay.update(
                    fps_display, output,
                    self.controller.current_velocity,
                    state, self.controller.current_key,
                    self.vision.debug_green_count,
                    self.vision.debug_yellow_count,
                    debug_frame,
                    difficulty=self._run_difficulty,
                    field2_frame=field2_frame,
                    field3_frame=None,
                )
                self.debug_overlay.process_events()

                self._cap_fps(t0, self.config.target_fps)

        except KeyboardInterrupt:
            print("\n[!] Interrupted by user.")
        finally:
            self.shutdown()

    def _change_field1(self):
        self._paused = True
        self.debug_overlay.root.destroy()
        print("\n[*] Selecting new Field 1...")
        field1 = select_roi("FIELD 1: drag over the fishing bar / current read area")
        if field1 is not None:
            self.config.field1 = field1
            self.config.roi = field1
            save_config(self.config)
            self.capture = ScreenCapture(field1.rect)
            print(f"[✓] Field 1 updated: {field1.rect}")
        else:
            print("[!] Field 1 selection cancelled.")
        self.debug_overlay = DebugOverlay(
            on_change_field1=self._change_field1,
            on_change_field2=self._change_field2,
            on_start=self._start_automation,
            on_stop=self._stop_automation
        )
        self._paused = False

    def _change_field2(self):
        self._paused = True
        self.debug_overlay.root.destroy()
        print("\n[*] Selecting new Field 2...")
        field2 = select_roi("FIELD 2: drag over second read area for difficulty OCR")
        if field2 is not None:
            self.config.field2 = field2
            save_config(self.config)
            if field2.valid:
                self.capture_field2 = ScreenCapture(field2.rect)
                self._recapture_field2 = True
                print(f"[✓] Field 2 updated: {field2.rect}")
            else:
                self.capture_field2 = None
                self._recapture_field2 = True
                print(f"[✓] Field 2 cleared")
        else:
            print("[!] Field 2 selection cancelled.")
        self.debug_overlay = DebugOverlay(
            on_change_field1=self._change_field1,
            on_change_field2=self._change_field2,
            on_start=self._start_automation,
            on_stop=self._stop_automation
        )
        self._paused = False

    def _start_automation(self):
        self._automation_enabled = True
        self._reset_field3_recovery()
        if self._last_state is None:
            self._field3_missing_start_time = time.perf_counter() - 5.0
            print("[BOT] Started. No green detected, recovery will start from mouse click.")
        else:
            print("[BOT] Started. Green detected, normal A/D control active.")

    def _stop_automation(self):
        self._automation_enabled = False
        self._reset_field3_recovery()
        self.controller.release_all()
        print("[BOT] Stopped automation.")

    def _reset_field3_recovery(self):
        self._field3_state = "idle"
        self._field3_missing_start_time = None
        self._field3_next_action_time = None
        self._field3_last_f_time = None
        self._field3_f_attempts = 0

    def _handle_field3_recovery(self, now):
        if self._field3_state == "stopped":
            return

        if self._field3_state == "idle":
            if self._field3_missing_start_time is None:
                self._field3_missing_start_time = now
                return

            if now - self._field3_missing_start_time < 5.0:
                return

            if self._field3_next_action_time is not None and now < self._field3_next_action_time:
                return

            self.controller.release_all()
            self.controller.click_mouse()
            self._field3_state = "wait_first_f"
            self._field3_next_action_time = now + 3.0
            self._field3_f_attempts += 1
            print(f"[FIELD3] No green for 5s, mouse clicked. Loop {self._field3_f_attempts}/5.")
            return

        if self._field3_state == "wait_first_f":
            if self._field3_next_action_time is not None and now < self._field3_next_action_time:
                return

            self.controller.release_all()
            self.controller.press_key("f")
            self._field3_state = "wait_second_f"
            self._field3_next_action_time = now + 7.0
            print(f"[FIELD3] Clicked F after mouse click. Loop {self._field3_f_attempts}/5.")
            return

        if self._field3_state == "wait_second_f":
            if self._field3_next_action_time is not None and now < self._field3_next_action_time:
                return

            self.controller.release_all()
            self.controller.press_key("f")
            print(f"[FIELD3] Clicked second F. Loop {self._field3_f_attempts}/5.")

            if self._field3_f_attempts >= 5:
                self._field3_state = "stopped"
                print("[FIELD3] Stopped after 5 recovery loops without green detection.")
                return

            self._field3_state = "idle"
            self._field3_missing_start_time = now
            self._field3_next_action_time = now + 5.0

    def _cap_fps(self, t_start, target_fps):
        elapsed = time.perf_counter() - t_start
        target = 1.0 / target_fps
        if elapsed < target:
            time.sleep(target - elapsed)

    def _detect_run_difficulty(self, field2_frame, state):
        now = time.perf_counter()
        
        if state is not None:
            self._consecutive_green += 1
            self._consecutive_green_miss = 0
        else:
            self._consecutive_green = 0
            self._consecutive_green_miss += 1
            if self._consecutive_green_miss >= 5 and self._run_difficulty is not None:
                print("[RUN] Green box lost for 5 frames. Resetting difficulty.")
                self._run_difficulty = None
                self._ocr_attempted = False
                self._consecutive_green_miss = 0
            return
        
        if self._run_difficulty is not None:
            return
        
        if self._ocr_attempted:
            return
        
        if self._consecutive_green < 3:
            return
        
        if now - self._last_ocr_attempt < 0.5:
            return
        self._last_ocr_attempt = now
        self._ocr_attempted = True
        
        if field2_frame is None:
            if not self._ocr_warned:
                print("[!] Field 2 frame not available for OCR.")
                self._ocr_warned = True
            return
        
        difficulties = sorted(
            [int(level) for level in self.config.difficulty_lengths.keys() if level.isdigit()],
            reverse=True,
        )
        
        try:
            from config import ROIConfig
            h, w = field2_frame.shape[:2]
            full_frame_roi = ROIConfig(x=0, y=0, w=w, h=h)
            detected = self.vision.detect_difficulty(field2_frame, difficulties, field2_roi=full_frame_roi)
        except Exception as e:
            if not self._ocr_warned:
                print(f"[!] OCR error: {e}")
                self._ocr_warned = True
            return
        
        if detected is None:
            if not self._ocr_warned:
                print("[!] OCR could not read difficulty. Using default.")
                self._ocr_warned = True
            return
        
        self._run_difficulty = detected
        width = float(self.config.difficulty_lengths.get(str(detected), 0))
        self.vision.assumed_green_w = width if width > 0 else None
        message = f"RUN_DIFFICULTY level={detected} assumed_green_w={width:.1f}"
        print(f"[READ OK] {message}")
        write_detection_log(message)

    def shutdown(self):
        self._running = False
        self.controller.release_all()
        if self.capture:
            self.capture.close()
        if self.debug_overlay:
            self.debug_overlay.set_running(False)
        cv2.destroyAllWindows()
        print("[✓] Bot stopped. All keys released.")


def main():
    parser = argparse.ArgumentParser(description="Auto-Fishing Bot for Rhythm/Minigame Bar")
    parser.add_argument("--recalibrate", action="store_true",
                        help="Force ROI re-selection on startup")
    parser.add_argument("--calibrate", action="store_true",
                        help="Launch HSV color calibration tool")
    parser.add_argument("--test", action="store_true",
                        help="Select Field 1/Field 2 and preview what Field 1 reads")
    parser.add_argument("--input-test", action="store_true",
                        help="Open a text field and test generated A/D input")
    args = parser.parse_args()

    if args.input_test:
        run_input_test_mode()
        return

    if args.test:
        run_test_mode()
        return

    if args.calibrate:
        from calibrator import run_calibrator
        run_calibrator()
        return

    if args.recalibrate:
        cfg = load_config()
        cfg.roi = None
        cfg.field1 = None
        save_config(cfg)
        print("[*] Cleared saved Field 1/ROI. Will prompt for new selection.")

    bot = FishingBot()
    bot.run()


if __name__ == "__main__":
    main()
