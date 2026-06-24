import os
import time
from typing import List

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GENERATED_LOG_PATH = os.path.join(_BASE_DIR, "generated_log.txt")
READ_LOG_PATH = os.path.join(_BASE_DIR, "read_log.txt")


class InputLogger:
    def __init__(self):
        self._generated_buffer: List[str] = []
        self._last_flush = time.time()

    def log_generated(self, message: str) -> None:
        print(message)
        self._generated_buffer.append(message)
        self._flush_generated()

    def log_read(self, message: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        line = f"[{stamp}] {message}\n"
        with open(READ_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)

    def _maybe_flush(self) -> None:
        now = time.time()
        if now - self._last_flush >= 1.0:
            self._flush_generated()
            self._last_flush = now

    def _flush_generated(self) -> None:
        if self._generated_buffer:
            stamp = time.strftime("%H:%M:%S")
            events = " | ".join(self._generated_buffer)
            line = f"[{stamp}] {events}\n"
            with open(GENERATED_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(line)
            self._generated_buffer.clear()
        self._last_flush = time.time()


_logger = InputLogger()


def write_generated_log(message: str) -> None:
    _logger.log_generated(message)


def write_read_log(message: str) -> None:
    _logger.log_read(message)


def clear_logs() -> None:
    for path in (GENERATED_LOG_PATH, READ_LOG_PATH):
        open(path, "w", encoding="utf-8").close()
