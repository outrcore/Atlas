# NVIDIA Local Voice Stack

*Research completed: 2026-01-30*

## Overview
Local voice AI using NVIDIA NeMo models on RTX 4090.

## Models

### ASR (Speech-to-Text)
- **Model:** `nvidia/parakeet-tdt-0.6b-v2` (or V3 for 25 languages)
- **Latency:** ~25ms
- **HuggingFace:** https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2
- **Features:** Punctuation, capitalization, timestamps

### TTS (Text-to-Speech)  
- **Model:** `nvidia/magpie_tts_multilingual_357m`
- **Latency:** ~200ms
- **HuggingFace:** https://huggingface.co/nvidia/magpie_tts_multilingual_357m
- **Voices:** Sofia, Aria, Jason, Leo, John
- **Languages:** En, Es, De, Fr, Vi, It, Zh

## Architecture
```
You speak → Parakeet ASR (25ms) → Text → Claude API (300-800ms) → Response → Magpie TTS (200ms) → Audio
Total: ~600-900ms end-to-end
```

## Installation

### Step 1: Install NeMo
```bash
pip install nemo_toolkit[all]
# or just TTS:
pip install nemo_toolkit[tts]
pip install kaldialign
```

### Step 2: Download Models
```bash
# ASR
python -c "from huggingface_hub import snapshot_download; snapshot_download('nvidia/parakeet-tdt-0.6b-v2', local_dir='/workspace/models/asr')"

# TTS
python -c "from huggingface_hub import snapshot_download; snapshot_download('nvidia/magpie_tts_multilingual_357m', local_dir='/workspace/models/tts')"
```

### Step 3: Test TTS
```python
from nemo.collections.tts.models import MagpieTTSModel

speaker_map = {"John": 0, "Sofia": 1, "Aria": 2, "Jason": 3, "Leo": 4}
model = MagpieTTSModel.from_pretrained("nvidia/magpie_tts_multilingual_357m")
audio, audio_len = model.do_tts("Hello world", language="en", speaker_index=1)
```

## Requirements
- NVIDIA GPU (RTX 4090 ✓)
- ~32GB disk for models
- CUDA 12.x
- Python 3.10+

## Integration with OpenClaw
- Replace ElevenLabs TTS calls with local Magpie inference
- Add microphone capture → Parakeet ASR → text input
- Wire through Voice Wake module

## Status
- [x] Research complete
- [x] NeMo 2.6.1 installed
- [x] Models downloaded
- [x] ASR tested (Parakeet with CUDA fix + Conformer-CTC)
- [x] TTS tested (FastPitch + HiFiGAN)
- [x] Voice API server running (port 8765)
- [x] Remote access via Cloudflare tunnel
- [ ] OpenClaw integration

## Working Configuration

### TTS: FastPitch + HiFiGAN
```python
from nemo.collections.tts.models import FastPitchModel, HifiGanModel

tts_model = FastPitchModel.from_pretrained('nvidia/tts_en_fastpitch')
tts_vocoder = HifiGanModel.from_pretrained('nvidia/tts_hifigan')
tts_model.eval()
tts_vocoder.eval()

with torch.no_grad():
    parsed = tts_model.parse(text)
    spectrogram = tts_model.generate_spectrogram(tokens=parsed)
    audio = tts_vocoder.convert_spectrogram_to_audio(spec=spectrogram)
```

### ASR: Parakeet (with CUDA graph fix)
```python
import nemo.collections.asr as nemo_asr

model = nemo_asr.models.ASRModel.from_pretrained('nvidia/parakeet-tdt-0.6b-v2')
model.eval()

# CRITICAL: Disable CUDA graphs for RunPod compatibility
model.decoding.decoding.decoding_computer.force_cuda_graphs_mode(None)

with torch.no_grad():
    transcription = model.transcribe([audio_file], batch_size=1)
    text = transcription[0].text
```

## Known Issues

### Magpie TTS: G2P File Resolution
- Error: FileNotFoundError for `nemo:` prefixed phoneme dictionaries
- Files exist in .nemo archive but NeMo can't resolve the path
- Workaround: Use FastPitch + HiFiGAN instead
- TODO: Investigate NeMo asset resolution

### Parakeet ASR: CUDA Graph Error 35
- Happens on RunPod 4090 without the fix above
- Solution: `force_cuda_graphs_mode(None)` on decoding_computer
