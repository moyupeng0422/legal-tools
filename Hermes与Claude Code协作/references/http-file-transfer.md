# HTTP Server File Transfer — Fallback When SCP Fails Over Tailscale Relay

## Problem

SCP over Tailscale DERP relay times out on files as small as 2.5MB. The relay connection (342ms ping, LA node) cannot sustain the bidirectional data flow for `scp`/`rsync`/SSH-pipe transfers of moderate-sized files.

## Solution: Python HTTP Server + curl

Start a simple static file server on the cloud, then have CC download the file via `curl` from Windows.

```mermaid
flowchart LR
    Hermes[Hermes (Cloud)] -->|python3 -m http.server PORT| HTTP[HTTP Server :18888]
    Windows[CC (Windows)] -->|curl http://100.90.24.4:18888/file| HTTP
    Hermes -->|tmux send-keys| Windows
```

### Step-by-step

**Cloud side (Hermes):**
```bash
# Write the file to share
write_file /tmp/my-task-file.md "<content>"

# Start HTTP server as background process
terminal(command="cd /tmp && python3 -m http.server 18888 --bind 0.0.0.0", background=true)

# Verify it's serving
curl -s -o /dev/null -w "%{http_code}" http://localhost:18888/my-task-file.md
# → 200
```

**Windows side (via CC tmux):**
Send a short instruction via tmux:
```bash
tmux send-keys -t claude-session 'curl -s http://100.90.24.4:18888/my-task-file.md -o C:\\Users\\HUAWEI\\my-task-file.md' Enter
```

**Cleanup:**
```bash
process(action="kill", session_id="proc_xxx")  # Kill the HTTP server
```

## Transfer Speed Notes

| File Size | Type | First Attempt | Second Attempt | Note |
|-----------|------|---------------|----------------|------|
| 4.7 KB | `.md` text | ✅ ~3s | — | Curl with default 15s timeout works fine |
| 2.6 MB | `.tar.gz` | ❌ timeout (1m) | ✅ ~90s (background) | Need 1m+ timeout; curl started in foreground timed out but was continued in background and succeeded |

**Key lesson for moderate files (1-10MB):** The default curl timeout (15s) will fail for 2.6MB files over relay. Either:
1. Set a longer timeout: `curl -s --max-time 120 http://...`
2. Or let curl run in background (CC will auto-continue)
3. Or use `--connect-timeout 15 --max-time 120` for a connect-timeout of 15s but total transfer timeout of 120s

## Why This Works When SCP Doesn't

| Method | Direction | Result |
|--------|-----------|--------|
| `scp -P 2222 file HUAWEI@100.107.207.104:C:/Users/...` | Cloud→Windows | ❌ Times out (60s+) |
| `cat file \| ssh -p 2222 HUAWEI@100.107.207.104 "powershell ..."` | Cloud→Windows | ❌ Times out (90s+) |
| `python3 -m http.server` on cloud, `curl` from Windows | Cloud→Windows | ✅ Works (small files fast, medium files ~90s) |

**Root cause:** SCP and SSH pipe both try to maintain bidirectional control channels alongside the data transfer. Over high-latency relay connections, the flow control stalls. HTTP is simpler — single-direction GET, no bidirectional state to maintain.

## Limitations

- Only works for the duration of the HTTP server process (don't rely on it for persistent access)
- Use ephemeral high ports (>1024) — no root needed
- The cloud's Tailscale IP (`100.90.24.4` for this setup) must be reachable from Windows
- Only HTTP (no HTTPS) — fine for local Tailscale network
- Kill the HTTP server when done — don't leave it running
- 2.6MB tar.gz took ~90s over relay; files >10MB may time out. Consider splitting large transfers.

## When to Use

- SCP/SCP-r times out but SSH works (`ssh -p 2222 HUAWEI@100.107.207.104 "echo OK"` succeeds)
- File is small enough for HTTP but SCP chokes (< 10MB files, expect 1-2 min for larger files)
- You need CC to download files from cloud for analysis (code structure review, config inspection)
