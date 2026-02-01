# Pomodoro Timer

**Status:** Complete ✓  
**Created:** 2026-01-30  
**Location:** `/workspace/projects/pomodoro/`

## Description
Terminal-based Pomodoro timer with rich TUI.

## Features
- 25min work / 5min break cycles
- Visual countdown with progress bar
- Color-coded (red=work, green=break)
- Keyboard controls: `p` pause, `r` reset, `q` quit
- Session counter for completed pomodoros
- Terminal bell on session end
- Blinking display when paused

## Files
- `main.py` — 133 lines, uses `rich` library
- `requirements.txt` — just `rich>=13.0.0`

## Run
```bash
cd /workspace/projects/pomodoro
pip install -r requirements.txt
python main.py
```

## Notes
- First project built with Claude Code
- Used to test Claude Code integration
