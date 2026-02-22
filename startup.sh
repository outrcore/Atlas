#!/bin/bash
# ATLAS Master Startup Script
# Run after RunPod restart to restore everything

set -e
echo "🚀 ATLAS Startup Sequence..."
echo ""

# ============================================
# 1. Claude Code Wrapper (gets wiped from /usr/local/bin)
# ============================================
echo "📦 Setting up Claude wrapper..."
cat > /usr/local/bin/claude << 'EOF'
#!/bin/bash
unset ANTHROPIC_API_KEY
exec /root/.claude/local/claude "$@"
EOF
chmod +x /usr/local/bin/claude
echo "   ✅ Claude wrapper installed"

# ============================================
# 2. Symlinks (if missing)
# ============================================
echo "🔗 Checking symlinks..."
[ ! -L ~/.openclaw ] && ln -sf /workspace/.openclaw ~/.openclaw && echo "   Created ~/.openclaw"
[ ! -L ~/clawd ] && ln -sf /workspace/clawd ~/clawd && echo "   Created ~/clawd"
[ ! -L ~/projects ] && ln -sf /workspace/projects ~/projects && echo "   Created ~/projects"
# Claude config - remove file if exists, then symlink
[ -f ~/.claude.json ] && [ ! -L ~/.claude.json ] && mv ~/.claude.json ~/.claude.json.bak
[ ! -L ~/.claude.json ] && ln -sf /workspace/clawd/.claude.json ~/.claude.json && echo "   Created ~/.claude.json"
echo "   ✅ Symlinks OK"

# ============================================
# 3. Voice Services (atlas-voice multi-agent system)
# ============================================
echo "🎙️ Starting voice services..."
if screen -ls | grep -q "atlas-voice"; then
    echo "   ⚠️ Voice services already running"
else
    # Get Anthropic API key from OpenClaw config
    ANTHROPIC_KEY=$(grep -o 'sk-ant-api[^"]*' /workspace/.openclaw/config.yaml 2>/dev/null | head -1)
    
    # Start atlas-voice (Edge TTS + Faster-Whisper + Claude)
    screen -dmS atlas-voice bash -c "cd /workspace/projects/atlas-voice && export ANTHROPIC_API_KEY=\"$ANTHROPIC_KEY\" && python web/server.py 2>&1 | tee /tmp/atlas-voice.log"
    echo "   ✅ Atlas Voice started (screen: atlas-voice, port 8800)"
fi

# ============================================
# 4. Discord Bot (Unified ATLAS - text + voice)
# ============================================
echo "💬 Starting Discord bot..."
if screen -ls | grep -q "atlas-discord"; then
    echo "   ⚠️ Discord bot already running"
else
    screen -dmS atlas-discord bash -c "cd /workspace/projects/atlas-discord && python -u bot.py 2>&1 | tee /tmp/atlas-discord.log"
    echo "   ✅ Discord bot started (screen: atlas-discord)"
fi

# ============================================
# 5. GPU Status
# ============================================
echo ""
echo "📊 GPU Status:"
nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader 2>/dev/null || echo "   GPU not available"

# ============================================
# 6. Service Health Check (after warmup)
# ============================================
echo ""
echo "⏳ Waiting for services to warm up (10s)..."
sleep 10

echo ""
echo "🩺 Health Check:"
screen -ls | grep -E "atlas-voice|atlas-discord" && echo "   ✅ Screen sessions running"

# ============================================
# Summary
# ============================================
echo ""
echo "============================================"
echo "🎉 ATLAS Startup Complete!"
echo ""
echo "Services:"
echo "  • Telegram: via OpenClaw gateway"
echo "  • Discord: atlas-discord (unified text + voice)"
echo "  • Voice Web: http://localhost:8800"
echo "  • Claude CLI: claude"
echo ""
echo "All instances share memory from /workspace/clawd/"
echo "Screen sessions: screen -ls"
echo "============================================"

# OAuth token persists in /workspace/clawd/.claude/.credentials.json (valid ~1 year)
