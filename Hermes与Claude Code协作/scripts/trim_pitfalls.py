#!/usr/bin/env python3
"""Trim SKILL.md Common Pitfalls from 43 entries to ~20 core high-frequency entries."""
import re
from pathlib import Path

# Core high-frequency pitfalls to keep (per plan criteria):
# - 启动序列/session
# - 弹窗/权限
# - accept edits 阻塞
# - 截断/发送
# - 协议 (ACK/DONE/task_map)
# - 传话/辩论
# - 监控
KEEP_NUMS = [
    '0',    # skill loading
    '1',    # Hermes prefs (variant a)
    '1',    # Web search retry (variant b - same number, will keep both as they were originally)
    '2',    # --dangerously-skip-permissions
    '5',    # resume vs continue
    '6',    # popup blind y
    '7',    # monitoring timeout
    '9',    # accept edits blocking
    '10',   # 传话 trap
    '12',   # interview two-beat
    '13',   # plan mode paste-buffer
    '15',   # over-planning
    '16',   # silent execution
    '18',   # task_map missing
    '20',   # send confirmation
    '26',   # real vs fake debate
    '27',   # interview form forward ban (variant a)
    '28',   # SSH disconnect capture-pane trap
    '33',   # DISCUSS over auto-suggest
    '36',   # idle rule
    '42',   # accept edits full blocking
]
# Numbers to remove (originally in SKILL.md pitfalls 0-42):
# 3, 4, 8, 11, 14, 17, 19, 21, 22, 23, 24, 25, 27b (Hermes 侧就近处理), 29, 30, 31, 32, 34, 35, 37, 38, 39, 40, 41

SKILL_PATH = Path('SKILL.md')
with SKILL_PATH.open(encoding='utf-8') as f:
    content = f.read()

# Find Common Pitfalls section
m = re.search(r'(## Common Pitfalls\n)(.*?)(\n\n> 详见 references/active-discussion-protocol\.md)', content, re.DOTALL)
if not m:
    print("ERROR: 未找到 Common Pitfalls 区段")
    exit(1)

header = m.group(1)
section = m.group(2)
footer = m.group(3)

# Parse pitfalls from section
lines = section.split('\n')
pitfalls = []
current = None
for line in lines:
    if line.startswith('## ') or line.startswith('### '):
        if current:
            pitfalls.append(current)
            current = None
        continue
    m2 = re.match(r'^(\d+)\.\s', line)
    if m2:
        if current:
            pitfalls.append(current)
        current = {'num': m2.group(1), 'lines': [line]}
    else:
        if current is not None:
            current['lines'].append(line)
if current:
    pitfalls.append(current)

# Filter: keep only pitfalls with num in KEEP_NUMS
# Note: keep ALL variants of same number (e.g., both #1 entries)
kept = [p for p in pitfalls if p['num'] in KEEP_NUMS]

# Rebuild section
new_section_lines = [header.rstrip('\n'), '']
for p in kept:
    for line in p['lines']:
        new_section_lines.append(line)
    # No extra blank line between pitfall entries (original had blank lines)
new_section_text = '\n'.join(new_section_lines)

# Replace
new_content = content[:m.start()] + new_section_text + content[m.end()-len(footer):]
# Actually, keep the footer too
new_content = content[:m.start()] + new_section_text + '\n' + footer + content[m.end():]

SKILL_PATH.write_text(new_content, encoding='utf-8')
print(f"Trimmed from {len(pitfalls)} to {len(kept)} pitfalls")
print(f"Kept nums: {[p['num'] for p in kept]}")
print(f"New line count: {len(new_content.split(chr(10)))}")
