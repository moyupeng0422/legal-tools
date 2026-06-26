#!/usr/bin/env python3
"""Extract all pitfalls from SKILL.md into references/pitfalls.md."""
import re
import sys
from pathlib import Path

SKILL_PATH = Path('SKILL.md')
OUT_PATH = Path('references/pitfalls.md')

with SKILL_PATH.open(encoding='utf-8') as f:
    content = f.read()

# Extract pitfalls region: from "## Common Pitfalls" to "## 未来方向"
m = re.search(r'## Common Pitfalls\n(.*?)## 未来方向', content, re.DOTALL)
if not m:
    print("ERROR: 未找到 pitfalls 区段", file=sys.stderr)
    sys.exit(1)
section = m.group(1)
lines = section.split('\n')

# Parse pitfalls. A pitfall starts at "N." or "Na." at start of line.
# Continuation includes: bare "v3.43" paragraphs (these are actually a separate pitfall we'll merge),
# bold-prefixed continuation paragraphs, code blocks, blank lines.
# Section ends at "## " or "### " heading.

pitfalls = []
current = None
in_codeblock = False

for line in lines:
    if line.strip().startswith('```'):
        in_codeblock = not in_codeblock
        if current:
            current['lines'].append(line)
        continue
    if in_codeblock:
        if current:
            current['lines'].append(line)
        continue

    # Skip the "v3.43 新增预防" bare paragraph - already covered by pitfall 42
    if re.match(r'^v3\.43 新增预防', line.strip()):
        if current:
            # Attach to current as continuation
            current['lines'].append('_（v3.43 新增预防段落：见相关 pitfall 的预防措施）_')
            current['lines'].append('')
        continue

    # Section headings end the current pitfall
    if line.startswith('## ') or line.startswith('### '):
        if current:
            pitfalls.append(current)
            current = None
        # Skip the section heading (these are misplaced "Reference 索引")
        continue

    # Check for pitfall start: number followed by dot at start
    m = re.match(r'^(\d+[a-z]?)\.\s', line)
    if m:
        if current:
            pitfalls.append(current)
        current = {'num': m.group(1), 'lines': [line]}
    else:
        if current is not None:
            current['lines'].append(line)
        # else: skip lines before first pitfall

if current:
    pitfalls.append(current)

# Now identify duplicates and assign a/b/c suffixes where content differs
from collections import defaultdict
groups = defaultdict(list)
for p in pitfalls:
    groups[p['num']].append(p)

# Process: for each number, check if entries are duplicates (same title) or distinct
def get_title(p):
    text = '\n'.join(p['lines'])
    m = re.search(r'\*\*(.+?)\*\*', text)
    if m:
        return m.group(1).strip()
    return ''

def normalize(s):
    # Normalize for comparison
    return re.sub(r'\s+', '', s.lower())

processed = {}  # final_num -> list of pitfalls with that final num
for num, plist in groups.items():
    titles = [(get_title(p), normalize(get_title(p))) for p in plist]
    # Group by normalized title
    title_groups = defaultdict(list)
    for i, (title, norm) in enumerate(titles):
        title_groups[norm].append(i)

    final = []
    suffix_idx = 0
    suffixes = ['', 'a', 'b', 'c', 'd']
    for norm, indices in title_groups.items():
        # All entries with same title -> take first, merge content if useful
        merged = plist[indices[0]]
        if len(indices) > 1:
            # True duplicate - merge but take longest
            merged = max([plist[i] for i in indices], key=lambda p: len('\n'.join(p['lines'])))
        if suffix_idx == 0:
            final_num = num
        else:
            final_num = f"{num}{suffixes[suffix_idx]}"
        merged['final_num'] = final_num
        merged['is_duplicate'] = len(indices) > 1 or len(title_groups) > 1
        merged['has_variant'] = len(title_groups) > 1
        final.append(merged)
        suffix_idx += 1
    processed[num] = final

# Get all final pitfalls sorted
def sort_key(p):
    m = re.match(r'(\d+)([a-z]?)', p['final_num'])
    return (int(m.group(1)), m.group(2))

all_final = []
for num in sorted(processed.keys(), key=lambda x: int(re.match(r'\d+', x).group())):
    all_final.extend(processed[num])
all_final.sort(key=sort_key)

# Categorize pitfalls by theme (rough keyword matching)
def categorize(p):
    title = get_title(p)
    text = '\n'.join(p['lines'])
    cats = []
    if any(k in title for k in ['启动', 'cd', '激活', 'resume', 'rename', 'session', 'tmux', '/clear']) or 'session' in title.lower():
        cats.append('启动序列/session 管理')
    if any(k in title for k in ['弹窗', '权限', 'interview', '审批', 'accept edits', 'permission', 'Do you want']):
        cats.append('弹窗/权限处理')
    if any(k in title for k in ['阻塞', '截断', 'paste-buffer', 'send-keys', 'SCP', '消息']):
        cats.append('消息发送/截断')
    if any(k in title for k in ['ACK', 'DONE', 'PAUSE', '协议', 'task_map', '状态摘要', '心跳']):
        cats.append('协议标记')
    if any(k in title for k in ['传话', '辩论', 'R1', 'R2', 'R3', '讨论', '讨论方向', '假辩论']):
        cats.append('传话/辩论')
    if any(k in title for k in ['监控', '方向', '卡住', '超时', '观察', 'Germinating', 'Blanching', 'Compacting']):
        cats.append('监控/超时')
    if any(k in title for k in ['编码', '中文路径', 'PowerShell', '$_', '乱码', 'Windows']):
        cats.append('编码/Windows 环境')
    if any(k in title for k in ['CC Web', 'Web Search', 'Explore', 'Search', '搜索']):
        cats.append('CC 工具行为')
    if any(k in title for k in ['法律', '条款', '公众号', '文章', '写作', 'markdown', '表格']):
        cats.append('写作协作')
    if any(k in title for k in ['批量', '分页', '数据', 'compact', 'context', 'JSON', '批次']):
        cats.append('批量任务/context')
    if any(k in title for k in ['SSH', 'Tailscale', '断连', 'relay', '连接']):
        cats.append('SSH/网络')
    if any(k in title for k in ['编译', 'code', '代码', 'MCP', 'Python', '脚本']):
        cats.append('代码审查')
    if not cats:
        cats.append('其他')
    return cats

# Write pitfalls.md
out = []
out.append("# Common Pitfalls (完整集)\n")
out.append("> SKILL.md 仅保留约 20 条核心高频条目，完整条目按原编号排列于此。")
out.append("> ")
out.append("> ## 编号规则\n")
out.append("> - **原始编号保留**：本文件保留 SKILL.md 中的原始编号（0–133），不重新编号，避免引用断链。")
out.append("> - **同号异义**：原始编号有重复且内容不同（如 #54 Playwright headed vs 非 ASCII 路径），按 a/b 后缀区分（如 #54a、#54b）。")
out.append("> - **同号同义**：原始编号重复但内容相同（如多次 copy-paste），合并为一条，取最完整版本。")
out.append("> - **已知断号**：#58、#63-#67、#82、#98、#124（编号体系已乱，实际使用未受影响，不补齐）。")
out.append("")

# Duplicate report
dup_report = []
for num, plist in groups.items():
    if len(plist) > 1:
        titles = [get_title(p)[:40] for p in plist]
        # Check if all same
        norms = set(normalize(t) for t in titles)
        if len(norms) == 1:
            dup_report.append(f"  - #{num}（×{len(plist)}，内容相同，已合并）")
        else:
            dup_report.append(f"  - #{num}（×{len(plist)}，内容不同，已用 a/b 后缀区分）")
out.append("## 重复编号处理记录\n")
out.append('\n'.join(dup_report))
out.append("")

# TOC by category
out.append("## Table of Contents（按类别分组）\n")
cat_groups = defaultdict(list)
for p in all_final:
    for c in categorize(p):
        cat_groups[c].append(p['final_num'])

cat_order = ['启动序列/session 管理', '弹窗/权限处理', '消息发送/截断', '协议标记', '传话/辩论',
             '监控/超时', '编码/Windows 环境', 'CC 工具行为', '写作协作', '批量任务/context',
             'SSH/网络', '代码审查', '其他']
for cat in cat_order:
    if cat in cat_groups:
        nums = cat_groups[cat]
        out.append(f"- **{cat}**: {', '.join(f'#{n}' for n in nums)}")
out.append("")

# Full pitfalls
out.append("## 全部 Pitfalls（按原编号顺序）\n")
for p in all_final:
    num = p['final_num']
    title = get_title(p)
    text = '\n'.join(p['lines']).strip()
    tag = ''
    if p.get('has_variant'):
        tag = ' _（同号变体之一）_'
    out.append(f"### #{num}. {title}{tag}\n")
    out.append(text)
    out.append("")

OUT_PATH.write_text('\n'.join(out), encoding='utf-8')

print(f"Generated {OUT_PATH}")
print(f"Total unique pitfalls: {len(all_final)}")
print(f"Original max number: 133")
print(f"Numbers covered: {len(set(p['final_num'] for p in all_final))}")
