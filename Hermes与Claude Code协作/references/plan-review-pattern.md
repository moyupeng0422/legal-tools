# Hermes→CC Plan Review Communication Pattern

## Problem

tmux `send-keys` has practical character limits for long natural-language messages.
When Hermes sends detailed review feedback (7+ items with rationale) directly via
`send-keys`, content can be truncated or split unpredictably, especially in
plan mode's option-4 text input.

## Solution: SCP File Transfer

1. Write review feedback to a local file (`/tmp/hermes-plan-reviewN.md`)
2. SCP to Windows: `scp -P 2222 /tmp/file.md <ssh-user>@<ssh-alias>:"<windows-userhome>/file.md"`
3. Send CC a short instruction to read the file: "读 <windows-userhome>\file.md，这是 Hermes 第 N 轮审查意见"
4. Verify delivery with `capture-pane` before proceeding

### Option-4 Input Quirk

Claude Code's plan approval dialog uses option 4 for free-text input.
To select it:
- Press `4` (not `Enter` first — `Enter` submits empty if option 1 is highlighted)
- Verify `>` cursor moves to option 4 via `capture-pane`
- Type or paste the instruction
- Press `Enter` to submit

## Multi-Round Review Workflow

1. **Round 1**: CC generates plan → Hermes reviews independently → sends feedback
2. CC updates plan, shows approval dialog again
3. **Round 2**: Hermes finds additional issues (e.g., values CC assumed without verifying) → sends second review
4. CC checks local config to confirm facts → updates plan → approval dialog

### Key Principle

Hermes must **independently verify facts** before flagging them as errors in CC's plan.
Counter-example (this session): Hermes flagged CC's API endpoint as "wrong" based on
Hermes's own config, but CC uses a different endpoint (Anthropic-compatible vs Coding Plan API).
The correct action was to ask CC to check its local settings, not assert Hermes's value as authoritative.

## Verification Checklist

After sending review file:
- [ ] `scp` returned exit code 0
- [ ] `capture-pane` shows CC received the read instruction (text visible in input)
- [ ] CC status changes from `⏸` to `✶`/`✻`/`✢` (processing)
