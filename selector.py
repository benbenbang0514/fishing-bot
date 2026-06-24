"""Transparent tkinter overlay for ROI selection."""

import tkinter as tk
from typing import Optional, Tuple


class ROIOverlay:
    def __init__(self, prompt: str = "Click and drag to select the fishing bar area."):
        self.root = tk.Tk()
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-alpha", 0.3)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="gray")

        self.canvas = tk.Canvas(self.root, bg="gray", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.start_x: Optional[int] = None
        self.start_y: Optional[int] = None
        self.rect_id: Optional[int] = None
        self.result: Optional[Tuple[int, int, int, int]] = None

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.root.bind("<Escape>", lambda e: self.root.destroy())

        self._label = tk.Label(
            self.root,
            text=f"{prompt}\nPress ESC to cancel.",
            font=("Arial", 16),
            fg="white",
            bg="black",
        )
        self._label.place(relx=0.5, rely=0.05, anchor="n")

    def _on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.rect_id:
            self.canvas.delete(self.rect_id)

    def _on_drag(self, event):
        if self.start_x is None or self.start_y is None:
            return
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            self.start_x, self.start_y, event.x, event.y,
            outline="red", width=2,
        )

    def _on_release(self, event):
        if self.start_x is None or self.start_y is None:
            return
        x1 = min(self.start_x, event.x)
        y1 = min(self.start_y, event.y)
        x2 = max(self.start_x, event.x)
        y2 = max(self.start_y, event.y)
        self.result = (x1, y1, x2 - x1, y2 - y1)
        self.root.after(300, self.root.destroy)

    def run(self) -> Optional[Tuple[int, int, int, int]]:
        self.root.mainloop()
        return self.result


def run_overlay_selector(prompt: str = "Click and drag to select the fishing bar area.") -> Optional[Tuple[int, int, int, int]]:
    overlay = ROIOverlay(prompt)
    return overlay.run()


if __name__ == "__main__":
    result = run_overlay_selector()
    if result:
        print(f"Selected ROI: x={result[0]}, y={result[1]}, w={result[2]}, h={result[3]}")
    else:
        print("Selection cancelled.")
