#!/usr/bin/env python3
"""Rebuild SKILL.md: remove duplicates, trim pitfalls, update description."""
import re
from pathlib import Path

SKILL_PATH = Path('SKILL.md')
OUT_PATH = Path('SKILL.md')  # in-place

with SKILL_PATH.open(encoding='utf-8') as f:
    content = f.read()

# === Step 1: Update description in frontmatter ===
old_desc = 'description: "Use when Hermes needs to orchestrate Claude Code on a local machine via SSH+tmux. Covers session management, monitoring, debate protocol, and error recovery."'
new_desc = 'description: "MANDATORY first skill to load when Hermes needs to orchestrate Claude Code on local Windows via SSH+tmux. Covers session lifecycle, monitoring (capture-pane), R1/R2/R3 debate protocol, error recovery, and bulk file transfer. Trigger whenever: (1) user requests local file operations/code modifications/script runs/Git ops on Windows; (2) Hermes needs to monitor CC execution and handle popups/errors; (3) post-execution verification is required before replying to user. Do NOT use when CC is connected via Feishu bridge — use feishu-agent-collab skill instead."'
assert old_desc in content, "old description not found"
content = content.replace(old_desc, new_desc)

# === Step 2: Add environment-config reference at top (after title) ===
env_ref = '\n> 📌 **环境特定值**（IP/路径/模型/SSH 配置）集中在 [references/environment-config.md](references/environment-config.md)。\n'
# Insert after "# Hermes × Claude Code 协作协议\n"
content = content.replace(
    '# Hermes × Claude Code 协作协议\n',
    '# Hermes × Claude Code 协作协议\n' + env_ref,
    1
)

# === Step 3: Remove bare "v3.43 新增预防" segments ===
# These appear inside SSH code block (line 267), inside duplicated Reference 索引 (line 277),
# and inside Common Pitfalls (line 449).
# Pattern: line starts with "v3.43 新增预防" (no leading whitespace)
bare_v343_pattern = re.compile(
    r'^v3\.43 新增预防.*?开始执行。.*?\n',
    re.MULTILINE
)
content = bare_v343_pattern.sub('', content)

# === Step 4: Remove first duplicated "## Reference 索引" block (line 271-280) ===
# Pattern: "## Reference 索引\n\n详细操作规范按需加载，不要一次性全部读取：\n\n| Reference | 内容 | 加载时机 |\n|-----------|------|---------|\n\n"
# followed by another "## Reference 索引" (the real one)
dup_pattern = re.compile(
    r'## Reference 索引\n\n详细操作规范按需加载，不要一次性全部读取：\n\n\| Reference \| 内容 \| 加载时机 \|\n\|-----------\|------\|---------\|\n\n',
    re.MULTILINE
)
content = dup_pattern.sub('', content)

# === Step 5: Verify only one "## Reference 索引" remains (will handle the second one which actually contains pitfalls) ===
# Count remaining "## Reference 索引"
count = len(re.findall(r'^## Reference 索引$', content, re.MULTILINE))
print(f"After step 4: ## Reference 索引 count = {count}")
assert count == 2, f"Expected 2 (first real + the misplaced pitfalls one), got {count}"

# === Step 6: Remove the misplaced second "## Reference 索引" header (which precedes pitfalls 43+) ===
# This is the one at line 453 that's followed by pitfalls instead of a reference table
# Pattern: "## Reference 索引\n43. **..."
content = re.sub(
    r'## Reference 索引\n(\d+\. \*\*)',
    r'\1',
    content,
    count=1,
    flags=re.MULTILINE
)

# === Step 7: Now the pitfalls section is one continuous block. Replace pitfalls 43+ with a short reference ===
# Find the end of Common Pitfalls: between "## Common Pitfalls" and the next "## " section after pitfall 42's block
# We'll keep pitfalls 0-42 (already trimmed by removing the v3.43 paragraph at the end),
# then replace everything from "43." onwards up to "### 双向心跳协议" with a reference link

# Strategy: find "43. **用户明确要求：两步确认法不可跳过"
# Replace from there up to "### 双向心跳协议" with our reference block.

# First, find the marker
marker = '### 双向心跳协议'
idx = content.find(marker)
assert idx != -1, "找不到 双向心跳协议 锚点"

# Find the start of pitfall 43
pit43_start = content.find('43. **用户明确要求')
assert pit43_start != -1, "找不到 pitfall 43 起点"

# Find the end of pitfall 42's block (just before 43)
# We want to keep pitfalls 0-42 and the "> 详见 references/active-discussion-protocol.md" line
# Look for the last newline before 43.
end_of_42 = content.rfind('\n', 0, pit43_start)
# Now look at what's between end_of_42 and pit43_start - should be minimal

# Replace from pit43_start to marker (exclusive) with our reference block
replacement = f"""
> 📋 以上为高频核心条目。完整 {134} 条 pitfalls（按原编号保留）详见 [references/pitfalls.md](references/pitfalls.md)。

"""

content = content[:pit43_start] + replacement + content[idx:]

# === Step 8: Also remove the bare "## Reference 索引" at line 453 that's now empty (since we replaced pitfalls) ===
# Wait - actually we need to check: did step 7 leave the misplaced Reference 索引 header?
# Let me check.
count_after = len(re.findall(r'^## Reference 索引$', content, re.MULTILINE))
print(f"After step 7: ## Reference 索引 count = {count_after}")

# === Step 9: Re-add proper Reference 索引 section after Common Pitfalls (or wherever it was) ===
# The first "## Reference 索引" (after step 4) is still there - that's the real one with the table.
# Let's verify the table content is intact by checking for "session-lifecycle" reference.

# Now let's check current state and write
OUT_PATH.write_text(content, encoding='utf-8')

# Verify
lines = content.split('\n')
print(f"Final line count: {len(lines)}")
print(f"Description: {new_desc[:80]}...")
