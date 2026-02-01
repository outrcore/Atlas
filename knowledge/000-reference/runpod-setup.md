# RunPod Server Setup

## Hardware
- **GPU:** NVIDIA RTX 4090
- **Memory:** 46GB
- **Storage:** 100GB persistent

## Access
- **IP/Port:** Dynamic! Check env vars on each restart:
  ```bash
  echo $RUNPOD_PUBLIC_IP
  echo $RUNPOD_TCP_PORT_22
  ```
- **User:** root
- **SSH:** `ssh root@$RUNPOD_PUBLIC_IP -p $RUNPOD_TCP_PORT_22`

## Persistence
- `/workspace/` survives restarts
- `/root/` does NOT survive restarts
- Symlink configs: `/root/.claude.json` → `/workspace/clawd/.claude.json`

## On Restart Checklist
1. Check if `/usr/local/bin/claude-code` wrapper exists
2. Recreate symlinks if needed
3. Re-run `/login` in Claude Code if OAuth expired
