"""批量任务输出文件完整性验证。检查：批次连续性、唯一性、源行覆盖、逐条消息覆盖。
用法：根据实际任务修改顶部配置项，scp 到 Windows 后 SSH 执行。
      python -u <windows-tmp>\batch-verify.py
"""
import glob, re, sys
from collections import Counter
sys.stdout.reconfigure(encoding='utf-8')

# ===== 配置（按实际任务修改）=====
OUTPUT_GLOB = r'<windows-tmp>\*人工筛选*.md'        # 输出文件 glob（含中文时用 glob 规避编码问题）
SOURCE_GLOB = r'<windows-tmp>\*过滤后*.md'           # 源文件 glob
SOURCE_MSG_PATTERN = r'\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}'  # 源文件中消息行的正则
EXPECTED_BATCH_RANGE = (1, 78)                 # 预期批次范围 (start, end)
# =================================

# 1. 源文件消息行统计
src_msgs = []
src_lines_count = 0
sf = sorted(glob.glob(SOURCE_GLOB))[0]
with open(sf, encoding='utf-8') as f:
    for i, line in enumerate(f, 1):
        src_lines_count += 1
        if re.match(SOURCE_MSG_PATTERN, line):
            src_msgs.append(i)
print(f'Source: {src_lines_count} lines, {len(src_msgs)} message lines')
print(f'  Message line range: {min(src_msgs)}-{max(src_msgs)}')

# 2. 输出文件分析
of = sorted(glob.glob(OUTPUT_GLOB))[0]
lines = open(of, encoding='utf-8').readlines()

# 2a. 批次连续性和唯一性
batch_count = Counter()
batch_ranges = {}
for l in lines:
    m = re.search(r'第(\d+)批', l)
    if m:
        batch_count[int(m.group(1))] += 1
    m2 = re.match(r'## 第(\d+)批[（(]行(\d+)-(\d+)', l)
    if m2:
        n, s, e = int(m2.group(1)), int(m2.group(2)), int(m2.group(3))
        batch_ranges[n] = (s, e)

all_expected = set(range(EXPECTED_BATCH_RANGE[0], EXPECTED_BATCH_RANGE[1]+1))
actual = set(batch_count.keys())
missing = sorted(all_expected - actual)
dupes = sorted([(k,v) for k,v in batch_count.items() if v > 1], key=lambda x:-x[1])

print(f'\n=== Batch Analysis ===')
print(f'Total headers: {sum(batch_count.values())}, Unique: {len(actual)}/{len(all_expected)}')
if missing: print(f'MISSING: {missing}')
if dupes: print(f'DUPLICATED: {dupes}')

# 2b. 保留/排除条目统计
keep_count = 0
exclude_count = 0
mode = 0  # 0=none, 1=keep, 2=exclude
for l in lines:
    s = l.strip()
    if s.startswith('### '):
        if '\u4fdd\u7559' in s: mode = 1   # "保留"
        elif '\u6392\u9664' in s: mode = 2  # "排除"
        else: mode = 0
    elif s.startswith('|') and not s.startswith('|--') and not s.startswith('| #'):
        if mode == 1: keep_count += 1
        elif mode == 2: exclude_count += 1

# K/E 编号格式条目（适配不同编号格式）
k_format = sum(1 for l in lines if re.match(r'\| K\d+ \|', l.strip()))
e_format = sum(1 for l in lines if re.match(r'\| E\d+ \|', l.strip()))
print(f'Keep entries: {keep_count} (K-format: {k_format})')
print(f'Exclude entries: {exclude_count} (E-format: {e_format})')
print(f'Total classified: {keep_count + exclude_count}')

# 3. 逐条消息覆盖分析（关键！）
# 从排除条目提取源文件行号范围
excluded_lines = set()
mode = 0
for l in lines:
    s = l.strip()
    if s.startswith('### '):
        if '\u4fdd\u7559' in s: mode = 1
        elif '\u6392\u9664' in s: mode = 2
        else: mode = 0
    elif mode == 2 and s.startswith('|') and not s.startswith('|--'):
        # 解析行号范围：| Exxx | 2310-2313 | 或 | Exxx | 2310,2317-2323 |
        parts = [p.strip() for p in s.split('|')]
        if len(parts) >= 3:
            range_str = parts[2]
            for seg in re.split(r'[,，]', range_str):
                seg = seg.strip()
                if '-' in seg:
                    a, b = seg.split('-')
                    try:
                        for ln in range(int(a.strip()), int(b.strip())+1):
                            excluded_lines.add(ln)
                    except ValueError:
                        pass
                else:
                    try: excluded_lines.add(int(seg))
                    except ValueError: pass

# 批次覆盖的消息行
all_batch_covered = set()
for n, (bs, be) in batch_ranges.items():
    for ln in range(bs, be+1):
        all_batch_covered.add(ln)

in_batch_msgs = set(src_msgs) & all_batch_covered
excluded_in_batch = in_batch_msgs & excluded_lines
kept_or_missed = in_batch_msgs - excluded_lines
unbatched_msgs = set(src_msgs) - all_batch_covered

print(f'\n=== Message Coverage ===')
print(f'Messages in batch ranges: {len(in_batch_msgs)}')
print(f'  Explicitly excluded: {len(excluded_in_batch)}')
print(f'  Kept or missed: {len(kept_or_missed)}')
print(f'    (Keep entries: {keep_count}, so MISSED = {len(kept_or_missed) - keep_count})')
print(f'Messages outside batch ranges: {len(unbatched_msgs)}')
if unbatched_msgs:
    nums = sorted(unbatched_msgs)
    ranges, start, end = [], nums[0], nums[0]
    for x in nums[1:]:
        if x == end + 1: end = x
        else: ranges.append((start, end)); start = end = x
    ranges.append((start, end))
    print(f'  Unbatched ranges: {ranges}')

total_missed = len(unbatched_msgs) + (len(kept_or_missed) - keep_count)
print(f'\n=== FINAL SUMMARY ===')
print(f'Source messages: {len(src_msgs)}')
print(f'Classified (K+E): {keep_count + exclude_count}')
print(f'Total MISSED (not K, not E): {total_missed}')
print(f'Coverage: {(len(src_msgs) - total_missed) / len(src_msgs) * 100:.1f}%')

# 4. Per-batch breakdown (for detailed investigation)
print(f'\n=== Per-Batch Breakthrough ===')
for bn in sorted(batch_ranges.keys()):
    bs, be = batch_ranges[bn]
    msgs = [l for l in src_msgs if bs <= l <= be]
    excl = [l for l in msgs if l in excluded_lines]
    note = ' **DUP**' if bn in missing or batch_count.get(bn,0)>1 else ''
    print(f'  Batch {bn:2d} (L{bs:4d}-{be:4d}): {len(msgs):3d} msgs, {len(excl):3d} excl, {len(msgs)-len(excl):3d} kept/missed{note}')
