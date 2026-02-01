# ATLAS Voice Stack Setup

*Last updated: 2026-01-31*

## Overview
Custom NVIDIA NeMo-based voice stack running on RunPod 4090 GPU.

## Components

### TTS (Text-to-Speech)
- **Models:** FastPitch + HiFiGAN
- **Speed:** ~0.18s for short sentences
- **Sample rate:** 22050 Hz
- **Quality:** Good, natural-sounding

### ASR (Speech-to-Text)
- **Model:** Parakeet TDT 0.6B v2
- **Speed:** Real-time
- **Accuracy:** Excellent punctuation and capitalization
- **Fix required:** CUDA graphs must be disabled

## Services

### Voice API v1 (port 8765)
- Basic TTS/ASR endpoints
- Simple HTML interface
- `/health`, `/tts`, `/asr`

### Voice API v2 (port 8766)
- Enhanced real-time interface
- Audio visualizer
- Microphone recording
- Session stats

## Access

### Local
```bash
curl http://localhost:8765/health
curl http://localhost:8766/health
```

### Remote
Cloudflare tunnel (URL changes on restart):
```bash
screen -dmS tunnel cloudflared tunnel --url http://localhost:8766
grep trycloudflare /tmp/tunnel.log
```

## Startup
```bash
/workspace/projects/voice-stack/start_services.sh
```

## Screen Sessions
- `voice_api` — v1 server
- `voice_v2` — v2 server
- `tunnel` — Cloudflare tunnel

## Logs
- `/workspace/projects/voice-stack/voice_api.log`
- `/workspace/projects/voice-stack/realtime_voice.log`
- `/tmp/tunnel.log`

## Known Issues

### Magpie TTS Not Working
- G2P phoneme dictionary resolution failing
- NeMo can't resolve `nemo:` protocol paths
- Using FastPitch as workaround

### CUDA Graphs Error (Parakeet)
Must disable CUDA graphs:
```python
model.decoding.decoding.decoding_computer.force_cuda_graphs_mode(None)
```

## Future Improvements
- [ ] Integrate with OpenClaw TTS system
- [ ] Real-time streaming via WebSocket
- [ ] Voice cloning / custom voices
- [ ] pipecat integration for conversations
