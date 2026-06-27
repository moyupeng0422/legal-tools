# CC + MCP Skill Development Pattern

Reusable pattern for when CC develops a Claude Code Skill that depends on an MCP server.

## When to Use

- CC is building a Skill that requires an external MCP server (e.g., wechat-decrypt, database, API)
- The MCP server needs to be configured in Claude Code before the Skill can function

## Config File (2026-06-06 corrected)

**Claude Code reads MCP servers from `~/.claude.json`**, NOT `~/.claude/mcp.json`.

Two levels:
| Level | File | Scope |
|-------|------|-------|
| **User MCPs** | `~/.claude.json` → `mcpServers` key | All Claude Code sessions |
| **Local MCPs** | `<project>/.claude.json` → `mcpServers` key | Project-specific only |

View via `/mcp` command. **Writing to `mcp.json` has NO effect — server won't appear in `/mcp` list.**

Also: `settings.json` → `enabledMcpjsonServers` is NOT required (2026-06-06: server was in enabledMcpjsonServers but still failed because it was only in `mcp.json`, not `.claude.json`).

## Workflow

```
1. CC clones/installs the MCP server code locally
2. CC installs Python/Node dependencies (pip install / npm install)
   - Long installs (>30s) will run in background; wait for completion
3. CC discovers the MCP server's transport mode (stdio/sse/http)
   - Most Python MCP servers use FastMCP stdio mode
   - Check: search for "mcp.run|__main__|if __name__" in server entry point
4. CC edits ~/.claude.json (User level) to add server under mcpServers:
   {
     "mcpServers": {
       "server-name": {
         "type": "stdio",
         "command": "python",
         "args": ["path/to/server.py"],
         "cwd": "/path/to/server/dir"
       }
     }
   }
5. CC restarts Claude Code session to load new MCP server
   - /mcp does NOT hot-reload; must /exit and restart claude
   - Hermes can send /mcp via tmux: send-keys '/mcp' Enter
6. CC verifies connectivity by calling a basic MCP tool (e.g., get_recent_sessions)
```

## Key Facts

- **Single config file**: `~/.claude.json` under `mcpServers` key. NO separate `mcp.json`.
- **No hot-reload**: MCP servers load at startup only. Must restart Claude Code after adding.
- **Hermes can send /mcp via tmux**: `send-keys '/mcp' Enter` works — slash commands route to CC REPL.
- **CC cannot execute /mcp via Bash**: `/mcp` is a REPL-internal command, not a shell command. CC must tell Hermes to do it.

## MCP stdio Server: stdout Pollution Pitfall (2026-06-06 confirmed)

MCP servers using stdio transport must **never write non-JSON-RPC content to stdout**. Any `print()` outputting to stdout will break the MCP client's JSON-RPC parser, causing the server to be marked "failed".

```python
# ❌ WRONG - breaks MCP stdio protocol
print(f"[DBCache] reused {reused} cached decrypted DBs", flush=True)

# ✅ CORRECT - logs go to stderr
print(f"[DBCache] reused {reused} cached decrypted DBs", file=sys.stderr, flush=True)
```

This was the root cause of wechat-decrypt MCP server "failed" status: `mcp_server.py` line 177 had a `print()` to stdout for cache status logging.

## R1→R2 Debate Points

When evaluating MCP vs CLI architecture for a Skill:

| Dimension | MCP | CLI |
|-----------|-----|-----|
| Tool count | Typically more (e.g., 17 vs 11) | Fewer commands |
| Extra capabilities | File decode, voice transcription, tag management | Output only |
| Deployment | Requires .claude.json + restart | Just install package |
| Stability | Long-running process, no public ban risk evidence | One-shot execution |
| Detection risk | Same as CLI (local Python, read-only, no network) | Same |

## Example: wechat-decrypt MCP

```json
// ~/.claude.json (add to existing mcpServers object)
"wechat-decrypt": {
  "type": "stdio",
  "command": "python",
  "args": ["<windows-tmp>/wechat-decrypt/mcp_server.py"],
  "cwd": "<windows-tmp>/wechat-decrypt"
}
```

Dependencies: FastMCP (pip), pycryptodome, zstandard.
Python path: `C:\Python314\python.exe` (Windows).
Verification: `get_recent_sessions` returns session list → MCP connected.

## General Principle: Empirical Verification via MCP (2026-06-07)

When designing Skill logic that depends on data field semantics (identifier formats, field presence, exclusion rules), **never guess or rely on training knowledge — call the MCP tool directly to verify with real data**.

Pattern:
```
1. Identify assumption to verify (e.g., "gh_ prefix = public account?")
2. CC calls MCP tool with known test cases (get_contacts, get_recent_sessions)
3. Confirm pattern across 3+ real samples
4. Write verified rule into SKILL.md
```

**Why**: MCP data semantics are implementation-specific and may differ from documentation or common knowledge. Empirical verification prevents incorrect rules in the Skill that waste future sessions debugging. Example: WeChat's `[群]` display suffix vs `@chatroom` username field — the latter is authoritative, but you can't know this without checking actual data.

## MCP Data Model Pitfalls (2026-06-07 discovered)

### wechat-decrypt: `get_contacts()` field gaps (2026-06-07 FIXED)

`get_contacts()` originally returned only 3 fields: `wxid`, `nickname`, `remark`. Tag information was NOT included, and there was no reverse-lookup API (contact → tags).

**Status: FIXED** — Modified `get_contacts()` in `mcp_server.py` (lines 2200-2211) to call existing `get_contact_tag_names_by_username()` function before the contact loop, building a reverse index once. Each contact's output now includes a `tags` field (list of tag names) when tags exist, or omitted when no tags.

**Remaining limitation**: No reverse-lookup API (contact → tags). To build a complete tag mapping, must iterate ALL tags via `get_tag_members(tag_name)` and construct a reverse index manually.

**Impact on Skill design**: A client-manage Skill that shows per-contact tags cannot rely on `get_contacts()` alone. Must add a tag iteration step (遍历所有标签 → get_tag_members → build contact→tags reverse map). With 32 tags this adds ~32 MCP calls but is the only way.

### WeChat identifier conventions (verified 2026-06-07)

| Type | Identifier Pattern | Examples |
|------|-------------------|----------|
| Public account / service | `wxid` starts with `gh_` | `gh_3dfda90e39d6` (微信支付), `gh_8d5e4fdcbe19` (格律法学院) |
| Personal account | `wxid_xxx` or custom string | `wxid_fw5zpb5hvtbc21`, `APELSEUS`, `q451307794` |
| System account | Special names | `filehelper` |
| Group chat | `username` contains `@chatroom` | Standard WeChat convention |
| Brand session placeholder | NOT in contacts table | `brandsessionholder`, `brandservicesessionholder` — appear in session list but `get_contacts()` returns empty |

**Programmatic detection rules** (for Skill logic):
- Public account: `get_contacts(query)` → check if `wxid` starts with `gh_`
- Group chat: `get_recent_sessions()` → check `username` for `@chatroom` (not `[群]` suffix in display text — that's a display artifact, not the authoritative field)
- Brand placeholders: `get_contacts()` returns empty → not a real contact

**CC pitfall observed**: CC used `[群]` suffix in display text instead of `@chatroom` in username for group detection. Skill should explicitly specify `@chatroom` field check, not display heuristic.

## MCP Server Code Change Hot-Reload (2026-06-07 discovered)

**stdio mode MCP servers do NOT auto-reload code changes.** The server process is persistent once started. Modifying `mcp_server.py` on disk has no effect until the process restarts.

**Reloading sequence:**
1. User manually restarts the MCP Server process (or Hermes sends `/mcp` via tmux to reconnect)
2. Verify with `Reconnected to <server-name>` in capture-pane
3. Call an MCP tool to confirm new behavior生效

**Pitfall: CC searching for process config spirals into permission popup hell.** When CC tries to find and kill the MCP server process, it may run 15+ `python -c` / `tasklist` commands, each triggering a permission popup. **Hermes should preemptively locate the config from cloud-side SSH** (search process list, read `.claude.json`), or simply tell CC to stop and have the user restart manually + `/mcp` reconnect.

**Example (wechat-decrypt, 2026-06-07):** Added `get_contact_tag_names_by_username()` reverse mapping to `get_contacts()` — 3 lines of code. CC spent 10+ minutes searching for the process config (not in mcp.json, not in settings.json). User manually restarted → `/mcp` reconnected → `get_contacts(query=章妍)` returned tags correctly.

## Troubleshooting: MCP Server "failed" Status

When `/mcp` shows server as "failed" with empty tool list:

### Step 1: Verify server not in wrong config file
```bash
# Check if server is in .claude.json (correct) or mcp.json (wrong)
python -c "import json; d=json.load(open(r'<windows-userhome>\.claude.json')); print('wechat-decrypt' in d.get('mcpServers',{}))"
python -c "import json; d=json.load(open(r'<windows-userhome>\.claude\mcp.json')); print(d.get('mcpServers',{}).keys())"
```

### Step 2: Verify server can start
```bash
timeout 5 python path/to/mcp_server.py 2>&1 || true
```
Normal: no output (stdio mode waits for client initialize message).

### Step 3: Verify Python environment consistency
```bash
python -c "from Crypto.Cipher import AES; import zstandard; from mcp.server.fastmcp import FastMCP; print('OK')"
```

### Step 4: Manual stdio handshake test (from Hermes SSH)
```bash
# PowerShell:
$json = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'
Set-Location <server_dir>
echo $json | python mcp_server.py
```
Should return JSON-RPC initialize response. If this works but Claude Code fails → problem is in Claude Code's MCP client or config file location.

### Step 5: Check for stdout pollution
Search server code for `print(` calls that output to stdout (not stderr). Any non-JSON on stdout will break stdio MCP protocol.

### Step 6: Restart Claude Code
`/mcp` cannot reload config. Must `/exit` and restart `claude`.
