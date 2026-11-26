# Hermes→CC Plan Review Communication Pattern

## Problem

tmux `send-keys` has practical character limits for long natural-language messages.
When Hermes sends detailed review feedback (7+ items with rationale) directly via
`send-keys`, content can be truncated or split unpredictably, especially in
plan mode's option-4 text input.

## Solution: SCP File Transfer

1. Write review feedback to a local file (`/tmp/hermes-plan-reviewN.md`)
2. SCP to Windows: `scp -P 2222 /tmp/file.md <windows-username>@local-win:"C:/Users/<windows-username>/file.md"`
3. Send CC a short instruction to read the file: "读 C:\Users\<windows-username>\file.md，这是 Hermes 第 N 轮审查意见"
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
Hermes's own config, but CC uses a different endpoint (Anthropic-compatible vs subscription API).
The correct action was to ask CC to check its local settings, not assert Hermes's value as authoritative.

## Pitfall: "Updated plan" ≠ All Sections Updated

CC claims "Updated plan" and immediately re-shows the execution confirmation dialog.
This does **not** mean all sections referenced in your feedback were actually modified.

**Symptom**: 5.1 table reflects your requested change, but 5.2 prose section still
carries the old description. CC updated the implementation table but forgot to
sync the delivery details.

**Mandatory verification after CC claims plan update**:
1. Note which section numbers you asked to change
2. SSH-read the specific section from the plan file (`type ... | sed -n 'START,ENDp'`)
3. Compare against your requested change — do not trust "Updated plan" text alone
4. If mismatch found → send targeted R2 follow-up citing the specific section number
   that still carries old text

**Root cause**: CC updates the most visible/editable section first, then the
confirmation dialog auto-triggers before CC revisits secondary sections that
reference the same change.

## Pitfall: "Updated plan" — Silent Total Failure Variant (2026-06-28)

Worse than the partial-update variant: CC claims "Updated plan" and
re-shows the confirmation dialog, but **no Edit was actually executed on the
target content**. The file is completely unchanged.

**Symptom**: `ssh local-win "type <plan_path>"` shows the exact same content as
before CC's claimed update. Multiple consecutive "Updated plan" claims, each
followed by the same confirmation dialog, with zero actual file changes.

**Root cause**: CC receives the modification instruction, processes it
internally, but the Edit hook errors (`PreToolUse:Edit hook error`) may cause
the Edit tool to silently fail in CC's internal tracking. CC then concludes
the edit succeeded and re-triggers the confirmation dialog.

**Option 4 as reliable fallback**: When CC's plan mode messages repeatedly fail
to produce actual file changes, switch to the **confirmation panel's option 4**
("Type here to tell Claude what to change"):

1. Navigate `>` to option 4 using Down keys
2. `capture-pane` verify `>` position
3. `Enter` to select
4. Type numbered modification instructions (e.g., "1) Title change to X
   2) Layout restore to Y 3) Delete Z")
5. `Enter` to submit

Option 4 forces CC to process the change request from a fresh input context
rather than from conversation history, which appears to be more reliable.

**Key lesson**: After ANY "Updated plan" claim, always SSH-read the plan file
to verify. Don't trust the claim. If verification fails multiple times, switch
to option 4.

Also see SKILL.md Pitfall #150 for the consolidated version.

## Verification Checklist

After sending review file:
- [ ] `scp` returned exit code 0
- [ ] `capture-pane` shows CC received the read instruction (text visible in input)
- [ ] CC status changes from `⏸` to `✶`/`✻`/`✢` (processing)
- [ ] After CC claims "Updated plan": SSH-read the specific section(s) you asked to change and verify text matches
