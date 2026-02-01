#!/usr/bin/env python3
"""
ATLAS System Status Check
Quick overview of all running services
"""

import subprocess
import urllib.request
import json
import os

def check_voice_api(port, name):
    """Check if voice API is running"""
    try:
        response = urllib.request.urlopen(f'http://localhost:{port}/health', timeout=5)
        data = json.loads(response.read().decode())
        status = '✅' if data.get('status') == 'healthy' else '⚠️'
        return f"{status} {name}: TTS={data.get('tts_loaded')}, ASR={data.get('asr_loaded')}"
    except Exception as e:
        return f"❌ {name}: {str(e)[:40]}"

def check_tunnel():
    """Get current tunnel URL"""
    try:
        with open('/tmp/tunnel.log', 'r') as f:
            content = f.read()
        import re
        match = re.search(r'https://[a-z-]+\.trycloudflare\.com', content)
        return match.group(0) if match else "Not found"
    except:
        return "Not running"

def check_gpu():
    """Get GPU status"""
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=utilization.gpu,memory.used,memory.total', '--format=csv,noheader'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(', ')
            return f"GPU: {parts[0]}, Memory: {parts[1]} / {parts[2]}"
    except:
        pass
    return "GPU: Unknown"

def check_screens():
    """List screen sessions"""
    try:
        result = subprocess.run(['screen', '-ls'], capture_output=True, text=True, timeout=5)
        lines = [l.strip() for l in result.stdout.split('\n') if 'Detached' in l or 'Attached' in l]
        return lines if lines else ["No sessions"]
    except:
        return ["screen not available"]

def main():
    print("=" * 50)
    print("🌐 ATLAS System Status")
    print("=" * 50)
    print()
    
    # Voice APIs
    print("📡 Voice Services:")
    print(f"   {check_voice_api(8765, 'Voice API v1')}")
    print(f"   {check_voice_api(8766, 'Voice API v2')}")
    print()
    
    # Tunnel
    print("🔗 Remote Access:")
    print(f"   Tunnel: {check_tunnel()}")
    print()
    
    # GPU
    print("🖥️  Hardware:")
    print(f"   {check_gpu()}")
    print()
    
    # Screen sessions
    print("📺 Screen Sessions:")
    for session in check_screens():
        print(f"   {session}")
    print()
    
    # Quick commands
    print("💡 Quick Commands:")
    print("   Start services: /workspace/projects/voice-stack/start_services.sh")
    print("   Attach screen:  screen -r <name>")
    print("   Check logs:     tail -f /workspace/projects/voice-stack/*.log")
    print()
    print("=" * 50)

if __name__ == "__main__":
    main()
