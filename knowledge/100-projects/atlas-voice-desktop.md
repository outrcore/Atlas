# ATLAS Voice & Desktop App

*Technical details about the voice interface and desktop application.*

## Voice Architecture

### Multi-Agent Design
```
     👂 EARS              🧠 MIND              👄 VOICE
   ┌─────────┐         ┌─────────┐         ┌─────────┐
   │ Haiku   │────────►│ Sonnet  │────────►│ Haiku   │
   │ ~100ms  │         │ ~500ms  │         │ ~100ms  │
   └─────────┘         └─────────┘         └─────────┘
   Always listening    Deep thinking       Backchanneling
   Intent detection    Tool use            Natural speech
   Emotion sensing     Memory              Interruption
```

### Components

| Component | Technology | Purpose |
|-----------|------------|---------|
| VAD | Silero VAD | Voice Activity Detection (~30ms per chunk) |
| STT | Faster-Whisper (distil-large-v3) | Speech-to-text transcription |
| TTS | Edge TTS (en-GB-RyanNeural) | British butler voice output |
| Brain | Claude (via OpenClaw) | Response generation |

### Key Settings
- VAD sensitivity: 0.3
- Silence threshold: 1000ms
- Audio chunk size: 512 samples
- Pre-roll buffer: Captures audio before VAD triggers

## Desktop App Evolution

### Iteration 1: PyWebView Wrapper
- Wrapped the web voice interface
- Problem: `navigator.mediaDevices.getUserMedia` not available

### Iteration 2: Native Tkinter + WebSocket
**Location:** `/workspace/projects/atlas-voice/desktop_native.py`

Features:
- Pure Python, no browser dependency
- Native mic access via sounddevice
- tkinter for GUI
- WebSocket connection to backend
- Animated orb UI
- Always-listening mode with VAD

### The Orb
- Pulsing animation when listening
- Different glow when speaking
- Click to start/stop
- Uses PIL for gradient rendering

## Technical Challenges Solved

### 1. Audio Chunking
VAD needs 512 samples but browser sends 4096. Solution: Split incoming audio into 512-sample chunks before VAD processing.

### 2. MP3 Playback
Server sends MP3, client tried to play as PCM. Solution: Use pydub to decode MP3 before playback.
```bash
pip install pydub
brew install ffmpeg  # pydub needs this
```

### 3. Continuous Listening
After speaking, ATLAS stopped listening. Solution: Non-blocking audio player in separate thread, continues capture while playing.

### 4. Interrupt Support
User talks while ATLAS speaking → ATLAS should stop. Solution: VAD-triggered interrupt signal, stops playback queue.

## Cloud vs Local

### Current: Cloud Backend (RunPod)
```
Mac Desktop App ──WebSocket──► Cloudflare Tunnel ──► RunPod
                                                     ├── Whisper (GPU)
                                                     ├── Claude (API)
                                                     └── Edge TTS
```
- Latency: Network round-trip
- Requires: Internet connection

### Potential: Fully Local (Mac)
Would use:
- `whisper.cpp` for STT (runs on Apple Silicon)
- `ollama` for the LLM
- `pyttsx3` or similar for TTS

Trade-off: Slower (no GPU) but zero latency to server, works offline.

## File Locations

```
/workspace/projects/atlas-voice/
├── main_v2.py              # Entry point
├── desktop_native.py       # Native Mac app
├── ARCHITECTURE_v2.md      # Design doc
├── shared/
│   ├── state.py            # Shared consciousness
│   └── events.py           # Event bus
├── agents/
│   ├── ears.py             # 👂 Haiku - listening
│   ├── mind.py             # 🧠 Sonnet - thinking
│   └── voice.py            # 👄 Haiku - speaking
└── audio/
    └── capture.py          # Mic/WebSocket/playback
```

## Running the Voice Interface

### Web Version
Accessible via Cloudflare tunnel at: `https://atlas-voice.mathewharrison.com`
(tunnel URL may change)

### Desktop Version
```bash
cd ~/Desktop/atlas-desktop/atlas-voice
git pull
pip3 install sounddevice websockets numpy pydub pillow
python3 desktop_native.py
```

---
*Created: 2026-02-04 | Source: Telegram export analysis*
