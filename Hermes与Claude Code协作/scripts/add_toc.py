#!/usr/bin/env python3
"""Add GitHub Flavored Markdown TOC to references files."""
import re
import sys
from pathlib import Path

FILES = [
    'error-recovery.md',
    'monitoring-debate.md',
    'acp-research.md',
    'session-lifecycle.md',
    'legal-article-collab-lessons.md',
    'batch-classification-hybrid.md',
    'skill-creation-workflow.md',
]

BASE = Path('references')

def slugify(text):
    """GFM anchor rules: lowercase, remove punctuation, spaces to hyphens.

    GitHub's algorithm:
    1. Lowercase
    2. Strip leading/trailing whitespace
    3. Replace whitespace with -
    4. Remove non-alphanumeric chars except - and _ (CJK chars preserved)
    """
    # Remove markdown formatting markers first
    s = re.sub(r'`|\*+|\[|\]|\(|\)', '', text)
    # Lowercase
    s = s.lower()
    # Replace whitespace with hyphens (do this before stripping punct)
    s = re.sub(r'\s+', '-', s.strip())
    # Remove punctuation that's not letter/number/hyphen/underscore/CJK
    # Keep: a-z, 0-9, -, _, and CJK ranges (\u4e00-\u9fff, \u3000-\u303f)
    s = re.sub(r'[^a-z0-9_\-\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]', '', s)
    # Collapse multiple hyphens
    s = re.sub(r'-+', '-', s)
    # Strip leading/trailing hyphens
    s = s.strip('-')
    return s

def build_toc(content):
    """Extract H2/H3 headings and build TOC. Skip TOC section if encountered."""
    lines = content.split('\n')
    toc_entries = []
    seen_slugs = {}  # for duplicate handling
    in_toc_section = False

    for line in lines:
        # Skip the TOC section itself (we just stripped it but be defensive)
        if line.strip() == '## Table of Contents':
            in_toc_section = True
            continue
        if in_toc_section:
            if line.strip() == '---':
                in_toc_section = False
            continue
        # Match ## or ### but not # (H1 is title) or ####+ (too deep)
        m = re.match(r'^(#{2,3})\s+(.+?)\s*$', line)
        if not m:
            continue
        level = len(m.group(1))
        title = m.group(2).strip()
        # Skip TOC itself
        if title.lower() == 'table of contents':
            continue
        slug = slugify(title)
        # GFM handles duplicates by appending -1, -2, etc.
        if slug in seen_slugs:
            seen_slugs[slug] += 1
            slug = f"{slug}-{seen_slugs[slug]}"
        else:
            seen_slugs[slug] = 0
        indent = '  ' * (level - 2)  # H2 = no indent, H3 = 2 spaces
        toc_entries.append(f"{indent}- [{title}](#{slug})")
    return toc_entries

def add_toc_to_file(filepath):
    content = filepath.read_text(encoding='utf-8')

    # Idempotency: if existing TOC block exists, remove it first
    # Match "## Table of Contents\n ... \n---\n" pattern
    content = re.sub(
        r'## Table of Contents\n.*?\n---\n\n?',
        '',
        content,
        count=1,
        flags=re.DOTALL,
    )

    lines = content.split('\n')

    # Find title (first H1)
    title_idx = None
    for i, line in enumerate(lines):
        if line.startswith('# '):
            title_idx = i
            break
    if title_idx is None:
        print(f"SKIP {filepath.name}: no H1 title found")
        return False

    toc_entries = build_toc(content)
    if not toc_entries:
        print(f"SKIP {filepath.name}: no H2/H3 headings found")
        return False

    # Find insertion point: after title and any following description/blank lines
    # Look for the next ## heading after the title - insert TOC before it
    insert_idx = None
    for i in range(title_idx + 1, len(lines)):
        if lines[i].startswith('## '):
            insert_idx = i
            break

    if insert_idx is None:
        # No ## section; insert at end
        insert_idx = len(lines)

    # Build TOC block
    toc_block = ['## Table of Contents', '']
    toc_block.extend(toc_entries)
    toc_block.extend(['', '---', ''])

    # Insert TOC + ensure a blank line before the next ##
    new_lines = lines[:insert_idx]
    if new_lines and new_lines[-1].strip() != '':
        new_lines.append('')
    new_lines.extend(toc_block)
    new_lines.extend(lines[insert_idx:])

    filepath.write_text('\n'.join(new_lines), encoding='utf-8')
    print(f"OK {filepath.name}: added {len(toc_entries)} TOC entries")
    return True

for fname in FILES:
    fp = BASE / fname
    if not fp.exists():
        print(f"MISSING {fname}")
        continue
    add_toc_to_file(fp)
