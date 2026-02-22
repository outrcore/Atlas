# ATLAS Desktop

**Type:** Desktop Voice Interface App  
**Status:** 🚧 In Development  
**Repo:** [github.com/outrcore/atlas-desktop-app](https://github.com/outrcore/atlas-desktop-app)

## Purpose

Desktop application for voice-based interaction with ATLAS. A local interface for chat, file management, and project work.

## Tech Stack

### Primary Version
- **Frontend:** React
- **Desktop Framework:** Tauri (Rust-based, lightweight)

### Alternative Version
- **Native:** Tkinter (Python)

## Features

| Feature | Description |
|---------|-------------|
| **Chat** | Conversational interface with ATLAS |
| **File Browser** | Navigate and manage local files |
| **Project Dashboard** | Overview of active projects |
| **Terminal** | Integrated terminal access |
| **Status Panel** | System/connection status display |

## Voice Input

**Push-to-talk** is preferred over touch-to-talk.
- More intentional activation
- Reduces accidental triggers
- Clearer conversation boundaries

## Architecture

```
┌─────────────────────────────────┐
│         React Frontend          │
├─────────────────────────────────┤
│      Tauri (Rust Bridge)        │
├─────────────────────────────────┤
│    Local FS │ API │ Voice       │
└─────────────────────────────────┘
```

## TODO

- [ ] Review current repo state
- [ ] Document build/run process
- [ ] Test voice integration
- [ ] Evaluate Tauri vs Tkinter trade-offs
