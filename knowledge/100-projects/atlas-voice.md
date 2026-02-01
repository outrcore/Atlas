# ATLAS Voice

**Location:** `/workspace/projects/atlas-voice/`
**Status:** In development
**Created:** 2026-01-31

## Overview

Real-time voice interface for ATLAS using a parallel multi-agent architecture. Goal is natural, human-like conversation with backchanneling, interruption handling, and low latency.

## Architecture (v2)

Three Claude agents running in parallel:

```
👂 EARS (Haiku)     🧠 MIND (Sonnet)      👄 VOICE (Haiku)
Always listening    Deep thinking         Always ready to speak
Intent detection    Tool use              Backchanneling
Emotion sensing     Memory                Natural speech
~100ms             ~500ms                 ~100ms
```

### Shared State
All agents share:
- Conversation history
- Current speaker (user/atlas/none)
- Emotional context
- Interruption state

### Event Bus
Agents communicate via async event queues:
- `TRANSCRIPT` → EARS analyzes
- `INTENT_DETECTED` → Routes to MIND or VOICE
- `THINKING_STARTED` → VOICE backchannels
- `RESPONSE_TOKEN` → VOICE speaks incrementally
- `INTERRUPT` → Everyone stops gracefully

## Components

### Audio Pipeline
- **VAD:** Silero VAD (~30ms per chunk)
- **STT:** Faster-Whisper distil-large-v3 (GPU)
- **TTS:** Edge TTS (en-GB-RyanNeural) - placeholder for Alfred voice

### Backchanneling
VOICE produces natural acknowledgments:
- While listening: "Mmhmm.", "I see.", "Go on."
- While MIND thinks: "Let me think...", "One moment..."

### Interruption Handling
1. EARS detects voice while VOICE is speaking
2. INTERRUPT event sent
3. VOICE stops, clears buffer
4. EARS processes new utterance

## Usage

```bash
cd /workspace/projects/atlas-voice

# Test components
python main_v2.py --test

# Simulate conversation (no mic needed)
python main_v2.py --simulate

# Live with microphone
python main_v2.py
```

## Dependencies

- silero-vad
- faster-whisper
- edge-tts
- anthropic (needs API key)
- sounddevice
- aiohttp
- websockets

## TODO

- [x] Wire up Claude API (direct key for now)
- [x] Add WebSocket server for browser access  
- [ ] Clone Alfred voice (ElevenLabs/XTTS)
- [ ] Test full end-to-end latency
- [ ] Add specialist agents (timer, weather, etc.)
- [ ] Optimize streaming (current: full audio accumulation)

## Voice Options (Edge TTS)

British male voices for Alfred-like tone:
- `en-GB-RyanNeural` - Currently used, good British accent
- `en-GB-ThomasNeural` - Alternative British voice
- `en-IE-ConnorNeural` - Irish accent, warm tone

For true Alfred voice cloning, need:
- 10-30 seconds of Michael Caine or Alfred audio
- ElevenLabs API key, or
- Local XTTS fine-tuning

## Files

```
atlas-voice/
├── ARCHITECTURE_v2.md     # Full design doc
├── main_v2.py             # Entry point
├── config.py              # Configuration
├── shared/
│   ├── state.py           # Shared consciousness
│   └── events.py          # Event bus
├── agents/
│   ├── ears.py            # 👂 Listening agent
│   ├── mind.py            # 🧠 Thinking agent
│   └── voice.py           # 👄 Speaking agent
├── audio/
│   └── capture.py         # Mic/playback pipeline
└── web/
    ├── server.py          # WebSocket server
    └── static/            # Browser UI
```
