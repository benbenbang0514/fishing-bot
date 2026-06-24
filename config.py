"""Configuration management: load/save ROI, HSV thresholds, key bindings."""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

DEFAULT_CONFIG = {
    "roi": None,
    "field1": None,
    "field2": None,
    "hsv_green": {"h_min": 30, "h_max": 90, "s_min": 70, "v_min": 70},
    "hsv_yellow": {"h_min": 10, "h_max": 45, "s_min": 40, "v_min": 140},
    "keys": {"left": "a", "right": "d"},
    "input_mode": "vk",
    "deadzone_percent": 0.15,
    "kp": 0.05,
    "target_fps": 60,
    "difficulty": 6,
    "difficulty_lengths": {"5": 145, "6": 125, "9": 63, "12": 70},
}


@dataclass
class HSVConfig:
    h_min: int = 30
    h_max: int = 90
    s_min: int = 70
    v_min: int = 70

    @property
    def lower(self):
        return (self.h_min, self.s_min, self.v_min)

    @property
    def upper(self):
        return (self.h_max, 255, 255)


@dataclass
class ROIConfig:
    x: int = 0
    y: int = 0
    w: int = 0
    h: int = 0

    @property
    def rect(self):
        return (self.x, self.y, self.w, self.h)

    @property
    def valid(self):
        return self.w > 0 and self.h > 0


@dataclass
class KeyConfig:
    left: str = "a"
    right: str = "d"


@dataclass
class BotConfig:
    roi: Optional[ROIConfig] = None
    field1: Optional[ROIConfig] = None
    field2: Optional[ROIConfig] = None
    field3: Optional[ROIConfig] = None
    hsv_green: HSVConfig = field(default_factory=HSVConfig)
    hsv_yellow: HSVConfig = field(default_factory=lambda: HSVConfig(h_min=10, h_max=45, s_min=40, v_min=140))
    keys: KeyConfig = field(default_factory=KeyConfig)
    input_mode: str = "vk"
    deadzone_percent: float = 0.15
    kp: float = 0.05
    target_fps: int = 60
    difficulty: int = 6
    difficulty_lengths: dict = field(default_factory=lambda: {"5": 145, "6": 125, "9": 63, "12": 70})

    def has_roi(self) -> bool:
        return self.roi is not None and self.roi.valid

    def active_roi(self) -> Optional[ROIConfig]:
        return self.field1 if self.field1 is not None and self.field1.valid else self.roi


def load_config() -> BotConfig:
    if not os.path.exists(CONFIG_PATH):
        return BotConfig()

    with open(CONFIG_PATH, "r") as f:
        data = json.load(f)

    cfg = BotConfig()

    for roi_key in ("roi", "field1", "field2", "field3"):
        if data.get(roi_key):
            roi_data = data[roi_key]
            setattr(cfg, roi_key, ROIConfig(
                x=roi_data["x"], y=roi_data["y"],
                w=roi_data["w"], h=roi_data["h"],
            ))

    for key in ("hsv_green", "hsv_yellow"):
        if key in data:
            hsv_data = data[key]
            setattr(cfg, key, HSVConfig(
                h_min=hsv_data.get("h_min", DEFAULT_CONFIG[key]["h_min"]),
                h_max=hsv_data.get("h_max", DEFAULT_CONFIG[key]["h_max"]),
                s_min=hsv_data.get("s_min", DEFAULT_CONFIG[key]["s_min"]),
                v_min=hsv_data.get("v_min", DEFAULT_CONFIG[key]["v_min"]),
            ))

    if "keys" in data:
        cfg.keys = KeyConfig(
            left=data["keys"].get("left", "a"),
            right=data["keys"].get("right", "d"),
        )

    cfg.deadzone_percent = data.get("deadzone_percent", 0.15)
    cfg.input_mode = data.get("input_mode", "vk")
    cfg.kp = data.get("kp", 0.05)
    cfg.target_fps = data.get("target_fps", 60)
    cfg.difficulty = data.get("difficulty", 6)
    cfg.difficulty_lengths = data.get("difficulty_lengths", DEFAULT_CONFIG["difficulty_lengths"])

    return cfg


def save_config(cfg: BotConfig) -> None:
    existing = {}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            existing = json.load(f)

    data = {
        "roi": asdict(cfg.roi) if cfg.roi else None,
        "field1": asdict(cfg.field1) if cfg.field1 else None,
        "field2": asdict(cfg.field2) if cfg.field2 else None,
        "field3": asdict(cfg.field3) if cfg.field3 else None,
        "hsv_green": asdict(cfg.hsv_green),
        "hsv_yellow": asdict(cfg.hsv_yellow),
        "keys": asdict(cfg.keys),
        "input_mode": existing.get("input_mode", cfg.input_mode),
        "deadzone_percent": existing.get("deadzone_percent", cfg.deadzone_percent),
        "kp": existing.get("kp", cfg.kp),
        "target_fps": existing.get("target_fps", cfg.target_fps),
        "difficulty": existing.get("difficulty", cfg.difficulty),
        "difficulty_lengths": existing.get("difficulty_lengths", cfg.difficulty_lengths),
    }
    with open(CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=2)


def update_hsv(cfg: BotConfig, color: str, hsv_data: dict) -> None:
    target = getattr(cfg, f"hsv_{color}")
    for k, v in hsv_data.items():
        setattr(target, k, v)
    save_config(cfg)
