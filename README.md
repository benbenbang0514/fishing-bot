# Auto-Fishing Bot
FOR neverness to everness NTE FISHING. THIS SHIT IS VIBE CODED with the remaining credit of my subscribtion quota lol. more like experiment on auto game pilot. works for me but never tested on other machine
A Python-based real-time computer vision bot that automates a fishing minigame. The bot detects a green target zone and a yellow player cursor on a horizontal bar, then sends A/D keystrokes to keep the cursor inside the target zone.

## Requirements

- **Python 3.10+**
- Windows (primary) or Linux

## Quick Start

### One-Click (Windows)

Double-click `start.bat`. It will:
1. Create a virtual environment (`.venv`) if missing
2. Install all dependencies
3. Launch the bot

### Manual Setup

```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (Linux/macOS)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the bot
python main.py
```

## Usage

### First Launch

1. Run `python main.py` (or `start.bat`)
2. A transparent overlay will appear — **click and drag** to draw a rectangle around the entire fishing bar area (include the fish icon on the left side)
3. The bot starts automatically after selection

### Calibration (Recommended)

Fine-tune color detection for your specific game:

```bash
python main.py --calibrate
```

- Press **G** to calibrate the green target zone
- Press **Y** to calibrate the yellow player cursor
- Adjust HSV trackbars until only the target color is visible in the mask
- Press **S** to save values
- Press **ESC** to exit

### Re-select ROI

```bash
python main.py --recalibrate
```

### Debug Overlay

```bash
python main.py --debug
```

Shows a live preview with detection bounding boxes, FPS, and control output.

## Anchor Template (Optional)

For more robust bar detection, create an anchor template:

1. Take a screenshot of the game while the fishing bar is visible
2. Crop out just the **fish icon + "魚耐力" text** area (small rectangle on the left side)
3. Save as `anchor_template.png` in the `fishing_bot/` directory
4. The bot will use template matching to locate the bar even if the game window moves

## Controls

| Key | Action |
|-----|--------|
| `A` | Move cursor left |
| `D` | Move cursor right |
| `Ctrl+C` (terminal) | Stop the bot |

## Configuration

All settings are stored in `config.json`:

| Setting | Default | Description |
|---------|---------|-------------|
| `roi` | — | Screen region to capture (set via overlay) |
| `hsv_green` | H:35-85, S:100+, V:100+ | Green target zone color range |
| `hsv_yellow` | H:20-35, S:100+, V:100+ | Yellow cursor color range |
| `keys.left` | `a` | Key for moving left |
| `keys.right` | `d` | Key for moving right |
| `deadzone_percent` | `0.15` | Deadzone as fraction of green zone width |
| `kp` | `0.05` | Proportional gain for PID controller |
| `target_fps` | `60` | Target frames per second |

## Project Structure

```
fishing_bot/
├── main.py              # Entry point: calibration → main loop
├── config.py            # Configuration load/save
├── capture.py           # Screen capture (mss)
├── vision.py            # CV pipeline: anchor + bar state
├── controller.py        # Input injection + PID logic
├── selector.py          # tkinter ROI selection overlay
├── calibrator.py        # HSV color calibration tool
├── requirements.txt     # Python dependencies
├── config.json          # Saved settings (auto-generated)
└── anchor_template.png  # Optional fish icon template
```

## Troubleshooting

- **Bot not detecting green/yellow**: Run `python main.py --calibrate` to tune HSV values for your game's specific colors
- **Keys not registering in game**: Try running the terminal as Administrator. Some games require elevated input injection
- **High CPU usage**: Lower `target_fps` in `config.json` (e.g., 30)
- **Cursor oscillates**: Increase `deadzone_percent` (e.g., 0.20) or decrease `kp` (e.g., 0.03)
