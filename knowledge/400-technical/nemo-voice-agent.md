# NeMo Voice Agent Framework

*Discovered: 2026-01-31*

## Overview
NeMo 2.6.0 includes a voice agent framework at `nemo.agents.voice_agent` that integrates with [pipecat](https://github.com/pipecat-ai/pipecat) for building real-time conversational AI.

## Components

### Location
`/usr/local/lib/python3.11/dist-packages/nemo/agents/voice_agent/`

### Key Modules
- **pipecat/services/nemo/stt.py** — Speech-to-Text service
- **pipecat/services/nemo/tts.py** — Text-to-Speech service
- **pipecat/services/nemo/llm.py** — LLM integration
- **pipecat/services/nemo/diar.py** — Speaker diarization
- **pipecat/services/nemo/turn_taking.py** — Conversation turn management
- **pipecat/transports/network/websocket_server.py** — WebSocket transport

### Features
- Real-time streaming audio via WebSocket
- Turn-taking for natural conversation flow
- Speaker diarization (multi-speaker support)
- Integration with pipecat pipeline framework

## Requirements
```bash
pip install pipecat-ai[websocket]
```

## Usage Pattern (Conceptual)
```python
from nemo.agents.voice_agent.pipecat.services.nemo import stt, tts
from nemo.agents.voice_agent.pipecat.transports.network import websocket_server

# Set up STT/TTS services
stt_service = stt.NeMoSTTService(model='parakeet-tdt-0.6b-v2')
tts_service = tts.NeMoTTSService(model='fastpitch')

# Create WebSocket server for real-time audio
transport = websocket_server.WebsocketServerTransport(host='0.0.0.0', port=8000)

# Pipeline: Audio -> STT -> LLM -> TTS -> Audio
```

## Future Work
- [ ] Test pipecat integration
- [ ] Build real-time voice conversation demo
- [ ] Integrate with OpenClaw for voice commands

## References
- [NeMo Voice Agent PR](https://github.com/NVIDIA-NeMo/NeMo/pull/14325)
- [pipecat documentation](https://github.com/pipecat-ai/pipecat)
