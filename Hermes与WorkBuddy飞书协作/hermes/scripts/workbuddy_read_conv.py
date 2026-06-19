#!/usr/bin/env python3
"""
Workbuddy conv 文件增量读取脚本。
通过 Base64-EncodedCommand 避免中文文件名编码问题。
只读取自上次读取以来新增的行，避免全文读取浪费 context。

用法：
  python3 badi_read_conv.py <conv_file_key>

conv_file_key 是文件名（如 conv_架构v3.0重构_20260619.md）。

输出：
  INCREMENTAL:<filename>:<N> new lines   + 仅新增行的内容
  NO_CHANGE:<filename>                   （无更新）
  SSH_FAIL:...                            （SSH 错误）
"""
import json, subprocess, sys, os, base64

TRACKER_PATH = os.path.expanduser("~/.hermes/badi_file_tracker.json")
SSH_HOST = "local-win"
CONV_DIR = r"D:\workbuddy\Claw\hermes_collab"

def load_tracker():
    if os.path.exists(TRACKER_PATH):
        with open(TRACKER_PATH, encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_tracker(tracker):
    with open(TRACKER_PATH, "w", encoding='utf-8') as f:
        json.dump(tracker, f, indent=2, ensure_ascii=False)
        f.flush()

def ps_encoded(cmd_text):
    """Encode PowerShell command as Base64 UTF-16LE for -EncodedCommand."""
    return base64.b64encode(cmd_text.encode('utf-16-le')).decode('ascii')

def ssh_ps(ps_cmd):
    """Run PowerShell via SSH with -EncodedCommand. Returns (stdout, stderr)."""
    encoded = ps_encoded(ps_cmd)
    full_cmd = ["ssh", SSH_HOST, "powershell", "-EncodedCommand", encoded]
    r = subprocess.run(full_cmd, capture_output=True, timeout=30)
    stdout = r.stdout.decode('utf-8', errors='replace')
    stderr = r.stderr.decode('utf-8', errors='replace')
    if r.returncode != 0:
        return None, stderr
    return stdout, None

def get_file_info(filename_filter):
    """Get filename and line count using wildcard filter."""
    ps_cmd = f"""
$f = Get-ChildItem -Path "{CONV_DIR}" -Filter "{filename_filter}" | Select-Object -First 1
if ($f -ne $null) {{
    Write-Output $f.Name
    $lines = (Get-Content -LiteralPath $f.FullName | Measure-Object -Line).Lines
    Write-Output $lines
}}
"""
    result, err = ssh_ps(ps_cmd)
    if result is None:
        return None, None
    lines = [l for l in result.strip().split('\n') if l.strip() and not l.startswith('#<')]
    if not lines:
        return None, None
    filename = lines[0].strip()
    try:
        total_lines = int(lines[1].strip())
    except (IndexError, ValueError):
        return None, None
    return filename, total_lines

def read_incremental_ps(filename_filter, skip_lines):
    """Read only new lines using wildcard filter."""
    if skip_lines == 0:
        ps_cmd = f"""
$f = Get-ChildItem -Path "{CONV_DIR}" -Filter "{filename_filter}" | Select-Object -First 1
if ($f -ne $null) {{ Get-Content -LiteralPath $f.FullName -Encoding UTF8 }}
"""
    else:
        ps_cmd = f"""
$f = Get-ChildItem -Path "{CONV_DIR}" -Filter "{filename_filter}" | Select-Object -First 1
if ($f -ne $null) {{ Get-Content -LiteralPath $f.FullName -Encoding UTF8 | Select-Object -Skip {skip_lines} }}
"""
    result, err = ssh_ps(ps_cmd)
    if result is None:
        return None
    clean = '\n'.join(l for l in result.split('\n') if not l.startswith('#<'))
    return clean.strip()

def build_filter(filename):
    """Build a wildcard filter from filename."""
    if '_' in filename:
        parts = filename.split('_')
        if len(parts) >= 3 and parts[0] == 'conv':
            return f"conv_{parts[1]}*.md"
    return filename.replace('.md', '*.md')

def main():
    if len(sys.argv) < 2:
        print("Usage: badi_read_conv.py <filename_key>", file=sys.stderr)
        sys.exit(1)

    file_key = sys.argv[1]
    tracker = load_tracker()
    name_filter = build_filter(file_key)

    actual_name, total = get_file_info(name_filter)
    if actual_name is None:
        print(f"SSH_FAIL: Cannot find file matching '{name_filter}'")
        sys.exit(1)

    last_info = tracker.get(file_key, {"last_lines": 0, "last_size": 0})
    if actual_name != file_key:
        last_info = tracker.get(actual_name, last_info)
        file_key = actual_name

    last_lines = last_info["last_lines"]
    if total <= last_lines:
        print(f"NO_CHANGE:{file_key}")
        sys.exit(0)

    new_content = read_incremental_ps(name_filter, last_lines)
    if new_content is None:
        print(f"SSH_FAIL: Cannot read content of {file_key}")
        sys.exit(1)

    tracker[file_key] = {
        "last_lines": total,
        "last_size": len(new_content) + last_info.get("last_size", 0)
    }
    save_tracker(tracker)

    print(f"INCREMENTAL:{file_key}:{total - last_lines} new lines")
    print(new_content)

if __name__ == "__main__":
    main()
