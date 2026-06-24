"""Input injection and control logic with velocity-aware smoothing.

Uses ctypes SendInput with scan codes as primary method for DirectX game compatibility.
Falls back to pydirectinput on non-Windows platforms.
"""

import numpy as np
import time
from typing import Optional, Dict
from dataclasses import dataclass
from input_log import write_generated_log

try:
    import ctypes
    from ctypes import wintypes
    HAS_CTYPES = True
except ImportError:
    HAS_CTYPES = False

try:
    import pydirectinput
    HAS_PYDIRECTINPUT = True
except ImportError:
    HAS_PYDIRECTINPUT = False

SCAN_CODES = {
    "a": 0x1E,
    "d": 0x20,
    "f": 0x21,
    "escape": 0x01,
}
VK_CODES = {
    "a": 0x41,
    "d": 0x44,
    "f": 0x46,
    "escape": 0x1B,
}

if HAS_CTYPES:
    wintypes.ULONG_PTR = wintypes.WPARAM
    INPUT_KEYBOARD = 1
    INPUT_MOUSE = 0
    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_SCANCODE = 0x0008
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", wintypes.ULONG_PTR),
        ]

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", wintypes.ULONG_PTR),
        ]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [
            ("uMsg", wintypes.DWORD),
            ("wParamL", wintypes.WORD),
            ("wParamH", wintypes.WORD),
        ]

    class INPUT_UNION(ctypes.Union):
        _fields_ = [
            ("mi", MOUSEINPUT),
            ("ki", KEYBDINPUT),
            ("hi", HARDWAREINPUT),
        ]

    class INPUT(ctypes.Structure):
        _fields_ = [
            ("type", wintypes.DWORD),
            ("union", INPUT_UNION),
        ]

    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _send_input = _user32.SendInput
    _send_input.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
    _send_input.restype = wintypes.UINT


@dataclass
class ControlState:
    output: float = 0.0
    prev_yellow_x: Optional[float] = None
    prev_time: Optional[float] = None
    velocity: float = 0.0


class InputController:
    def __init__(self, left_key: str = "a", right_key: str = "d",
                 deadzone_percent: float = 0.15, kp: float = 0.05,
                 input_mode: str = "vk"):
        self.left_key = left_key.lower()
        self.right_key = right_key.lower()
        self.deadzone_percent = deadzone_percent
        self.kp = kp
        self.input_mode = input_mode.lower()
        self._state = ControlState()
        self._left_held = False
        self._right_held = False

    def compute(self, green_x: float, green_w: float, yellow_x: float,
                dt: float) -> float:
        state = self._state

        if state.prev_yellow_x is not None and dt > 0:
            state.velocity = (yellow_x - state.prev_yellow_x) / dt

        predicted = yellow_x + state.velocity * dt
        target = green_x + green_w / 2.0
        error = target - predicted

        buffer = green_w * self.deadzone_percent
        if green_x + buffer < predicted < green_x + green_w - buffer:
            state.output = 0.0
        else:
            state.output = float(np.clip(error * self.kp, -1.0, 1.0))

        state.prev_yellow_x = yellow_x
        state.prev_time = time.perf_counter()

        return state.output

    def send_input(self, output: float) -> None:
        if output < -0.2:
            self._hold_left()
        elif output > 0.2:
            self._hold_right()
        else:
            self._release_both()

    def _hold_left(self):
        if self._right_held:
            self._release_right()
        if not self._left_held:
            self._key_down(self.left_key)
            self._left_held = True

    def _hold_right(self):
        if self._left_held:
            self._release_left()
        if not self._right_held:
            self._key_down(self.right_key)
            self._right_held = True

    def _release_both(self):
        self._release_left()
        self._release_right()

    def _release_left(self):
        if self._left_held:
            self._key_up(self.left_key)
            self._left_held = False

    def _release_right(self):
        if self._right_held:
            self._key_up(self.right_key)
            self._right_held = False

    def release_all(self):
        self._release_both()

    def press_key(self, key: str, duration: float = 0.05):
        self._key_down(key)
        time.sleep(duration)
        self._key_up(key)

    def click_mouse(self, duration: float = 0.05):
        if HAS_CTYPES:
            self._sendinput_mouse(MOUSEEVENTF_LEFTDOWN)
            time.sleep(duration)
            self._sendinput_mouse(MOUSEEVENTF_LEFTUP)
        elif HAS_PYDIRECTINPUT:
            pydirectinput.click()
            write_generated_log("mouse=LEFT action=CLICK method=pydirectinput")

    def _key_down(self, key: str):
        if HAS_CTYPES:
            self._sendinput_key(key, down=True, mode=self.input_mode)
        elif HAS_PYDIRECTINPUT:
            pydirectinput.keyDown(key)
            write_generated_log(f"key={key.upper()} action=DOWN method=pydirectinput")

    def _key_up(self, key: str):
        if HAS_CTYPES:
            self._sendinput_key(key, down=False, mode=self.input_mode)
        elif HAS_PYDIRECTINPUT:
            pydirectinput.keyUp(key)
            write_generated_log(f"key={key.upper()} action=UP method=pydirectinput")

    @staticmethod
    def _sendinput_key(key: str, down: bool, mode: str = "vk"):
        vk = VK_CODES.get(key, 0)
        scan = SCAN_CODES.get(key, 0)
        flags = 0 if mode == "vk" else KEYEVENTF_SCANCODE
        if not down:
            flags |= KEYEVENTF_KEYUP

        ki = KEYBDINPUT(vk if mode == "vk" else 0, scan if mode != "vk" else 0, flags, 0, 0)
        inp = INPUT(INPUT_KEYBOARD, INPUT_UNION(ki=ki))
        sent = _send_input(1, ctypes.byref(inp), ctypes.sizeof(inp))
        error = ctypes.get_last_error() if sent != 1 else 0
        action = "DOWN" if down else "UP"
        write_generated_log(
            f"key={key.upper()} action={action} "
            f"method=SendInput mode={mode} vk=0x{vk:02X} scan=0x{scan:02X} sent={sent}/1 error={error}"
        )

    @staticmethod
    def _sendinput_mouse(flags: int):
        mi = MOUSEINPUT(0, 0, 0, flags, 0, 0)
        inp = INPUT(INPUT_MOUSE, INPUT_UNION(mi=mi))
        sent = _send_input(1, ctypes.byref(inp), ctypes.sizeof(inp))
        error = ctypes.get_last_error() if sent != 1 else 0
        action = "LEFTDOWN" if flags == MOUSEEVENTF_LEFTDOWN else "LEFTUP"
        write_generated_log(
            f"mouse=LEFT action={action} method=SendInput sent={sent}/1 error={error}"
        )

    @staticmethod
    def _read_key_pressed(key: str) -> bool:
        vk = VK_CODES.get(key.lower())
        if not HAS_CTYPES or vk is None:
            return False
        return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)

    @staticmethod
    def read_all_keys() -> Dict[str, bool]:
        return {
            "A": InputController._read_key_pressed("a"),
            "D": InputController._read_key_pressed("d"),
        }

    @property
    def current_output(self) -> float:
        return self._state.output

    @property
    def current_velocity(self) -> float:
        return self._state.velocity

    @property
    def current_key(self) -> str:
        if self._left_held:
            return self.left_key.upper()
        elif self._right_held:
            return self.right_key.upper()
        return "-"
