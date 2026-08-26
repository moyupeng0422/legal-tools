"""cron_rmfyalk_import.py — 案例数据库自动导入脚本

功能（纯脚本，零 LLM 介入）:
  1. 检查 rmfyalk token → 过期则自动登录
  2. 执行 11 个 v3 检索任务（sort_id 精确检索）
  3. 去重（processed_ids.json）
  4. 导出新增案例 → 格式清洗 → 写入 staging
  5. 更新 processed_ids.json

运行方式:
  python cron_rmfyalk_import.py

依赖:
  - rmfyalk MCP 项目（client.py, export_formatter.py）
  - login_rmfyalk.py（自动登录）
  - 不需要 MCP server（直接调用 API）
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Windows GBK 终端不支持 emoji，强制 stdout/stderr 为 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── 路径配置 ──────────────────────────────────────────────────────

# rmfyalk MCP 项目根：脚本所在目录的上级（自动推导，不硬编码本地路径）
MCP_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = MCP_DIR / "scripts"

# 导出根目录：优先 .env 的 EXPORT_DIR；未设置则用项目内 _data（公开仓库不含本地路径）
_EXPORT_ROOT = (
    Path(os.getenv("EXPORT_DIR"))
    if os.getenv("EXPORT_DIR")
    else MCP_DIR / "_data"
)

# 输出目录
STAGING_DIR = _EXPORT_ROOT / "_staging" / "cases"
PROCESSED_JSON = STAGING_DIR / "processed_ids.json"

# 日志
LOG_FILE = STAGING_DIR / "cron_log.txt"

# 加入 Python path 以便 import client.py
sys.path.insert(0, str(SCRIPTS_DIR))

# ── v3 检索策略（11 个 sort_id + 4 个关键词兜底） ─────────────

SEARCH_TASKS = [
    # (sort_id, label) — sort_id 精确检索
    ("20000527", "知识产权合同纠纷（父级）"),
    ("20000528", "知识产权权属侵权（父级）"),
    ("20000529", "不正当竞争纠纷（父级）"),
    ("20000530", "垄断纠纷（父级）"),
    ("30000024", "专利行政"),
    ("30000025", "专利行政-2"),
    ("30000026", "专利行政-3"),
    ("30000027", "专利行政-4"),
    ("30000028", "专利行政-5"),
    ("30000029", "商标行政"),
    ("30000030", "商标行政-2"),
    ("30000023", "行政通用"),
]

# 关键词兜底检索（覆盖 sort_id 无法命中的边缘 IP 类型）
# 这些案例在 sort_id 体系中属于刑事/侵权责任/执行等非 IP 分类，
# 但内容与知识产权直接相关，用关键词 + 指导性案例过滤来捕获
KEYWORD_FALLBACKS = [
    # (keyword, label, search_field)
    ("知识产权 假冒 商标 版权 专利", "IP刑事/行政边缘（87号类）", "qw"),
    ("知识产权 财产损害", "IP侵权责任边缘（222号类）", "qw"),
    ("知识产权 执行", "IP执行案件（251号类）", "qw"),
]

GLOBAL_SEARCH_PARAMS = {
    "court": None,               # 不限制
    "sort_field": "",            # 默认排序
    "page": 1,
    "page_size": 50,
}

# 案例类型：仅指导性案例（参考案例数量庞大，不通过 cron 自动导入）
CASE_TYPES = ["guiding"]

LOGIN_SCRIPT = str(SCRIPTS_DIR / "login_rmfyalk.py")


# ── 日志 ──────────────────────────────────────────────────────────


def log(msg: str) -> None:
    """同时输出到 stdout 和日志文件。"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    try:
        STAGING_DIR.mkdir(parents=True, exist_ok=True)
        with open(str(LOG_FILE), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


# ── Token 检查 ────────────────────────────────────────────────────


def _decode_jwt_exp(token: str) -> float:
    """解码 JWT exp 返回剩余分钟数。"""
    import base64
    if not token or "." not in token:
        return -1
    parts = token.split(".")
    if len(parts) != 3:
        return -1
    try:
        payload_b64 = parts[1]
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        exp = payload.get("exp", 0)
        if not exp:
            return -1
        return max(0, (exp - time.time()) / 60)
    except Exception:
        return -1


def ensure_token() -> bool:
    """确保 rmfyalk token 有效，过期则自动登录。

    Returns:
        True 如果 token 可用
    """
    from client import client as rmfyalk_client

    token = rmfyalk_client.token
    remaining = _decode_jwt_exp(token)

    if token and remaining > 5:
        log(f"Token 有效，剩余 {remaining:.0f} 分钟")
        return True

    log("Token 过期或不可用，启动自动登录...")
    try:
        result = subprocess.run(
            [sys.executable, LOGIN_SCRIPT],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            # 重新加载 token（client 启动时从 .env 读取，但运行时需要手动同步）
            from client import client as rmfyalk_client
            rmfyalk_client._sync_from_tokens_json()
            token = rmfyalk_client.token
            remaining = _decode_jwt_exp(token)
            log(f"登录成功！Token 剩余 {remaining:.0f} 分钟")
            return True
        else:
            log(f"登录失败 (exit {result.returncode})")
            log(f"  stdout: {result.stdout[-500:]}")
            log(f"  stderr: {result.stderr[-500:]}")
            return False
    except subprocess.TimeoutExpired:
        log("自动登录超时（>120秒）")
        return False
    except Exception as e:
        log(f"自动登录异常: {e}")
        return False


# ── 网络自检 + 状态记录（P0：防 VPN/代理静默失败） ───────────────

STATUS_FILE = STAGING_DIR / "last_run_status.md"


async def check_network() -> tuple[bool, str]:
    """探测 rmfyalk 连通性，检测 VPN/代理干扰。

    用与 client 相同的 aiohttp TLS 栈探测公开根路径（无 token），
    能真实反映后续 API 调用的可达性。VPN 开启时此处会 SSL EOF/连接失败。

    Returns:
        (True, "网络正常...") 或 (False, 错误描述)
    """
    import aiohttp
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(
            timeout=timeout, connector=aiohttp.TCPConnector(ssl=False)
        ) as s:
            async with s.get("https://rmfyalk.court.gov.cn/") as r:
                if r.status == 200:
                    return True, "网络正常（rmfyalk 可达）"
                return False, f"rmfyalk 返回 HTTP {r.status}（非 200）"
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:200]}"


def write_cron_status(
    status: str,
    message: str,
    error_type: str = "none",
    duration_sec: float = 0,
    search_total: int = 0,
    exported: int = 0,
    skipped: int = 0,
) -> None:
    """写 cron 运行状态到 last_run_status.md（Obsidian 可见，Dataview 可聚合）。

    Args:
        status: success / failed / network_error
        message: 状态描述或失败原因
        error_type: none / network / token / search / export
        duration_sec: 本次耗时
        search_total: 检索结果总数
        exported: 导出数
        skipped: 去重跳过数
    """
    now = datetime.now()
    status_emoji = {
        "success": "✅ 成功",
        "failed": "❌ 失败",
        "network_error": "⚠️ 网络异常",
    }
    try:
        STAGING_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        return

    lines = [
        "---",
        "type: cron-status",
        f"status: {status}",
        f"error_type: {error_type}",
        f"timestamp: {now.strftime('%Y-%m-%d %H:%M:%S')}",
        f"date: {now.strftime('%Y-%m-%d')}",
        f"duration_sec: {int(duration_sec)}",
        f"search_total: {search_total}",
        f"exported: {exported}",
        f"skipped: {skipped}",
        "---",
        "",
        "# Cron 导入状态",
        "",
        f"- **状态**: {status_emoji.get(status, status)}",
        f"- **时间**: {now.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **耗时**: {int(duration_sec)} 秒",
        f"- **原因**: {message}",
        "",
    ]
    if status != "success":
        lines.extend([
            "## 排查建议",
            "",
            "- 检查是否开启 **VPN/代理**——已确认 VPN 会干扰 rmfyalk 的 TLS 连接（SSL EOF/RST），关闭后重跑",
            "- 手动重跑：`cd scripts && python cron_import.py`",
            "- 详细日志：`_staging/cases/cron_log.txt`",
            "",
        ])
    else:
        lines.extend([
            "## 统计",
            "",
            f"- 检索结果: {search_total} 条",
            f"- 新增导出: {exported} 篇",
            f"- 去重跳过: {skipped} 篇",
            "",
        ])

    try:
        with open(str(STATUS_FILE), "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines))
    except OSError as e:
        log(f"写状态文件失败: {e}")


# ── 检索 ──────────────────────────────────────────────────────────


async def search_task(
    client, sort_id: str, label: str
) -> list[dict]:
    """执行单个 sort_id 检索任务（指导性+参考案例分别检索合并）。

    Returns:
        搜索结果列表
    """
    all_items: list[dict] = []

    for case_type in CASE_TYPES:
        log(f"  检索: {label} [{case_type}] (sort_id={sort_id})")

        body = client.build_search_body(
            keyword="",
            sort_id=sort_id,
            case_type=case_type,
            page=GLOBAL_SEARCH_PARAMS["page"],
            page_size=GLOBAL_SEARCH_PARAMS["page_size"],
            sort_field=GLOBAL_SEARCH_PARAMS["sort_field"],
        )

        import asyncio as _asyncio
        await _asyncio.sleep(0.3)  # 单次请求间防爬

        try:
            result = await client.post("cpwsAl/search", body)
            data = result.get("data", {})
            items = data.get("datas", [])
            total = data.get("totalCount", 0)
            log(f"    → 共 {total} 条，返回 {len(items)} 条")
            all_items.extend(items)
        except Exception as e:
            log(f"    ❌ 检索失败: {e}")

    return all_items


async def search_keyword_fallback(
    client, keyword: str, label: str, search_field: str = "qw"
) -> list[dict]:
    """关键词兜底检索（仅指导性案例，覆盖 sort_id 无法命中的边缘类型）。

    Returns:
        搜索结果列表
    """
    all_items: list[dict] = []

    for case_type in CASE_TYPES:
        log(f"  关键词兜底: {label} [{case_type}] ({keyword})")

        body = client.build_search_body(
            keyword=keyword,
            search_field=search_field,
            case_type=case_type,
            page=GLOBAL_SEARCH_PARAMS["page"],
            page_size=GLOBAL_SEARCH_PARAMS["page_size"],
            sort_field=GLOBAL_SEARCH_PARAMS["sort_field"],
            match_type="fuzzy",
        )

        await asyncio.sleep(0.3)

        try:
            result = await client.post("cpwsAl/search", body)
            data = result.get("data", {})
            items = data.get("datas", [])
            total = data.get("totalCount", 0)
            log(f"    → 共 {total} 条，返回 {len(items)} 条")
            all_items.extend(items)
        except Exception as e:
            log(f"    ❌ 检索失败: {e}")

    return all_items


# ── 去重 ──────────────────────────────────────────────────────────


def load_processed_ids() -> set[str]:
    """加载已处理案例编号集合。

    Returns:
        set 格式：{"115", "162", ...}
    """
    if not PROCESSED_JSON.exists():
        log("processed_ids.json 不存在，将创建新缓存")
        return set()

    try:
        with open(str(PROCESSED_JSON), "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return {item["case_id"] for item in data if item.get("case_id")}
        elif isinstance(data, dict) and "processed" in data:
            return {item["case_id"] for item in data["processed"] if item.get("case_id")}
        else:
            log("processed_ids.json 格式异常，将重建")
            return set()
    except (json.JSONDecodeError, OSError, KeyError) as e:
        log(f"读取 processed_ids.json 失败: {e}，将重建")
        return set()


def save_processed_ids(processed: list[dict]) -> None:
    """保存 processed_ids.json。"""
    try:
        STAGING_DIR.mkdir(parents=True, exist_ok=True)
        with open(str(PROCESSED_JSON), "w", encoding="utf-8") as f:
            json.dump(processed, f, ensure_ascii=False, indent=2)
        log(f"processed_ids.json 已更新，共 {len(processed)} 条")
    except OSError as e:
        log(f"保存 processed_ids.json 失败: {e}")


def _extract_case_id_from_title(title: str) -> str:
    """从标题提取案例编号。

    "指导性案例279号：西某..." → "279"
    "参考案例100号" → "100"
    """
    import re
    # 先脱 HTML（搜索结果含 <em> 标签）
    title_clean = re.sub(r'<[^>]+>', '', title)
    m = re.search(r'(?:指导性案例|指导案例|参考案例)\s*(\d+)\s*号', title_clean)
    if m:
        return m.group(1)
    return ""


def dedup(
    all_results: list[dict], processed_ids: set[str]
) -> tuple[list[dict], list[dict]]:
    """去重（按案例编号从标题提取后比对）。

    Args:
        all_results: 所有搜索结果的合并列表
        processed_ids: 已处理案例编号集合（如 {"115", "162"}）

    Returns:
        (new_cases, skipped): 新增案例列表、被跳过的案例列表
    """
    seen: set[str] = set()
    new_cases: list[dict] = []
    skipped: list[dict] = []

    for item in all_results:
        title = item.get("cpws_al_title", "") or ""
        case_id = _extract_case_id_from_title(title)
        if not case_id:
            continue  # 无法提取编号的跳过（不应发生）
        if case_id in seen:
            continue  # 同批结果中重复
        seen.add(case_id)

        if case_id in processed_ids:
            skipped.append(item)
        else:
            new_cases.append(item)

    return new_cases, skipped


# ── 导出与格式清洗 ──────────────────────────────────────────────


IP_DIR_MAP = {
    "专利": "001-专利",
    "商标": "002-商标",
    "著作权": "003-著作权",
    "商业秘密": "004-商业秘密",
    "不正当竞争": "004-商业秘密",
    "植物新品种": "005-植物新品种",
    "反垄断": "006-反垄断",
    "集成电路": "001-专利",
    "数据权益": "007-知识产权综合",
}

DEFAULT_DIR = "007-知识产权综合"

DEST_DIR = _EXPORT_ROOT / "司法案例数据库"

CASE_TYPE_LABELS = {
    "01": "指导性案例",
    "02": "参考案例",
}


def _clean_title(raw_title: str) -> str:
    """清洗标题：去除 HTML 标签、前缀、转半角符号。"""
    title = raw_title.strip()
    # 去除 HTML 标签（搜索结果中的 <em> 高亮）
    import re
    title = re.sub(r'<[^>]+>', '', title)
    # 去除 "指导案例N号：" / "指导性案例N号：" / "参考案例N号：" 前缀
    title = re.sub(r'^(?:指导性案例|指导案例|参考案例)\d+号\s*[:：]?\s*', '', title)
    return title


def _strip_html(text: str) -> str:
    """HTML 转纯文本：标签→换行、实体→字符、去多余空格。

    处理流程:
      1. HTML 标签 → 换行（保留段落结构）
      2. HTML 实体 → 字符
      3. 残留标签清除
      4. 全角空格清除
      5. 行内段落断行（句号/分号后识别新段落起始，插入换行）
      6. 换行后段落间距标准化（在已有换行的段落起始前加空行）
      7. 清理多余空行
      8. 行首行尾空格清除
    """
    if not text:
        return ""
    import re
    # 1. 关键：保留段落结构
    text = re.sub(r'</p>\s*<p', '\n\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</(?:p|div|li|h\d)>', '\n', text, flags=re.IGNORECASE)

    # 2. 转换 HTML 实体
    text = text.replace("&nbsp;", " ").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'")

    # 3. 去掉残留的 HTML 标签
    text = re.sub(r'<[^>]+>', '', text)

    # 4. 去掉全角空格缩进（API 用 4 个全角空格做段落缩进）
    text = text.replace("　　", "")
    text = text.replace("　", "")

    # 5. 行内段落断行：在句子结束符后识别新段落起始并插入换行。
    #    解决 API 返回纯文本无任何分隔符时段落黏连的问题。
    _se = r'([。；！？）》””])'  # 句子结束符（含捕获组，\1引用）
    # 5a. "其一""其二"等
    text = re.sub(_se + r'\s*(其[一二三四五六七八九十]+[，、])', r'\1\n\n\2', text)
    # 5b. 转折/总结/递进词
    text = re.sub(
        _se + r'\s*(此外|鉴此|综上(?:所述)?|据此|故(?:而|以)?|因此|所以|然而|但是|'
        r'同时|之后|并且|对于|关于|参照|根据|依照|按照|本案中)',
        r'\1\n\n\2', text,
    )
    # 5c. 年份开头
    text = re.sub(_se + r'\s*(\d{4}年)', r'\1\n\n\2', text)
    # 5d. 法院名开头
    text = re.sub(_se + r'\s*([一-鿿]{2,6}(?:中级|高级|基层)?人民法院)', r'\1\n\n\2', text)
    # 5e. 中文序号
    text = re.sub(_se + r'\s*([一二三四五六七八九十]+、)', r'\1\n\n\2', text)
    # 5f. 括号序号
    text = re.sub(_se + r'\s*([（(][一二三四五六七八九十\d]+[）)])', r'\1\n\n\2', text)
    # 5g. 数字序号
    text = re.sub(_se + r'\s*(\d+[.、)])', r'\1\n\n\2', text)
    # 5h. "为"字开头的目的句式
    text = re.sub(_se + r'\s*(为[“"”])', r'\1\n\n\2', text)

    # 6. 在已有换行的段落起始前加空行（标准化段落间距）
    text = re.sub(r'\n(一、|二、|三、|四、|五、|六、|七、|八、|九、|十、)', r'\n\n\1', text)
    text = re.sub(r'\n([（(][一二三四五六七八九十\d]+[）)])', r'\n\n\1', text)
    text = re.sub(r'\n(\d+[.、)])', r'\n\n\1', text)
    text = re.sub(r'\n(其[一二三四五六七八九十]+[，、])', r'\n\n\1', text)
    text = re.sub(r'\n(此外|鉴此|综上(?:所述)?|据此|故(?:而|以)?|因此|所以|然而|但是|同时|之后|并且|对于|关于|参照|根据|依照|按照|本案中)', r'\n\n\1', text)
    text = re.sub(r'\n(\d{4}年)', r'\n\n\1', text)
    text = re.sub(r'\n([一-鿿]{2,6}(?:中级|高级|基层)?人民法院)', r'\n\n\1', text)
    text = re.sub(r'\n(为[“"”])', r'\n\n\1', text)

    # 7. 清理多余空行（保留段落级的双换行）
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+\n', '\n', text)

    # 8. 去掉行首行尾的多余空格
    lines = [l.strip() for l in text.split('\n')]
    text = '\n'.join(lines)

    return text.strip()


def _get_case_prefix(case_type: str) -> str:
    """根据案例类型获取文件名前缀。"""
    return CASE_TYPE_LABELS.get(case_type, "案例")


def _format_date(date_str: str) -> str:
    """统一日期格式：YYYY-MM-DD"""
    if not date_str:
        return ""
    return date_str.replace(".", "-")


def _clean_case_number(case_no: str) -> str:
    """统一案号为半角括号。"""
    if not case_no:
        return ""
    return case_no.replace("（", "(").replace("）", ")").replace(" ", "")


def _classify_ip_type(sort_name: str, title: str) -> tuple[str, str]:
    """判断 IP 类型和目标目录。"""
    text = f"{sort_name} {title}".lower()
    for ip_type, keywords in [
        ("专利", ["专利"]),
        ("商标", ["商标"]),
        ("著作权", ["著作权", "计算机软件"]),
        ("商业秘密", ["商业秘密", "技术秘密"]),
        ("植物新品种", ["植物新品种"]),
        ("反垄断", ["垄断"]),
        ("不正当竞争", ["不正当竞争", "虚假宣传", "仿冒", "混淆", "商业诋毁", "擅自使用"]),
        ("集成电路", ["集成电路"]),
        ("数据权益", ["数据"]),
    ]:
        for kw in keywords:
            if kw in text:
                return ip_type, IP_DIR_MAP.get(ip_type, DEFAULT_DIR)
    return "综合", DEFAULT_DIR


async def export_case(
    client, item: dict
) -> dict | None:
    """导出单个案例并写入 staging。

    Args:
        item: 搜索结果中的案例条目

    Returns:
        导出结果的 dict（含 case_id, category, filename），或 None
    """
    import re

    title_raw = item.get("cpws_al_title", "") or ""
    case_type_code = item.get("cpws_al_type", "01")
    sort_name = item.get("cpws_al_sort_name", "") or ""
    case_number = _clean_case_number(item.get("cpws_al_ajzh", "") or "")
    encrypted_id = item.get("cpws_al_id", "") or ""  # 用于详情 API 调用

    # 从标题提取案例编号
    case_id = _extract_case_id_from_title(title_raw)
    if not case_id:
        log(f"  ❌ 无法从标题提取案例编号: {title_raw[:40]}")
        return None

    # ── 清洗标题 ──
    clean_title = _clean_title(title_raw)
    prefix = _get_case_prefix(case_type_code)

    # ── 获取详情 ──
    try:
        detail = await client.post("cpwsAl/content", {"gid": encrypted_id})
    except Exception as e:
        log(f"  ❌ 案例 {case_id} 详情获取失败: {e}")
        return None

    case_data = detail.get("data", {}).get("data", {})
    if not case_data:
        log(f"  ❌ 案例 {case_id} 详情为空")
        return None

    # ── 提取字段（详情 API 优先，搜索结果补缺） ──
    # 裁判日期：详情 API 用 cpws_al_zs_date，搜索结果也可提供
    judgment_date = _format_date(
        case_data.get("cpws_al_zs_date", "") or item.get("cpws_al_zs_date", "") or ""
    )
    court = _strip_html(
        case_data.get("cpws_al_fymc", "") or item.get("cpws_al_slfy_name", "") or ""
    ).strip()
    # 案号：搜索结果中有，详情中可能没有
    case_no_clean = _clean_case_number(
        case_data.get("cpws_al_ajzh", "") or item.get("cpws_al_ajzh", "") or ""
    )
    # 发布机关：搜索结果中有
    publish_org = item.get("cpws_al_sf", "") or "最高人民法院"

    keywords_raw = case_data.get("cpws_al_keyword", "") or ""
    ip_type, subdir = _classify_ip_type(sort_name, clean_title)

    # 关键词：可能是字符串（空格分隔）或列表
    if isinstance(keywords_raw, list):
        keywords = "/".join(k for k in keywords_raw if k)
    elif isinstance(keywords_raw, str):
        keywords = keywords_raw.replace(" ", "/") if keywords_raw else ""
    else:
        keywords = ""

    # ── 构建 frontmatter（中文字段名，对齐 SCHEMA） ──
    case_number_int = int(case_id) if case_id.isdigit() else 0

    frontmatter = {
        "title": f'"{clean_title}"',
        "案例编号": case_number_int,
        "案例类型": f'"{prefix}"',
        "发布机关": f'"{publish_org}"',
        "审理法院": f'"{court}"',
        "案号": f'"{case_no_clean}"',
        "裁判日期": judgment_date,
        "案由": f'"{sort_name}"',
        "IP类型": f'"{ip_type}"',
        "来源": "人民法院案例库",
        "tags": [],
        "引用建立": "[否]",
    }

    # ── 正文 ──
    body_parts = []

    # 关键词段落
    if isinstance(keywords_raw, list):
        kw_text = "/".join(k for k in keywords_raw if k)
    elif isinstance(keywords_raw, str):
        kw_text = keywords_raw.replace(" ", "/") if keywords_raw.strip() else ""
    else:
        kw_text = ""
    if kw_text:
        body_parts.append(f"## 关键词\n\n{kw_text}")

    field_map = [
        ("cpws_al_cpyz", "## 裁判要点"),
        ("cpws_al_glsy", "## 相关法条"),
        ("cpws_al_jbaq", "## 基本案情"),
        ("cpws_al_cpjg", "## 裁判结果"),
        ("cpws_al_cply", "## 裁判理由"),
    ]

    for field, heading in field_map:
        content = case_data.get(field, "") or ""
        if content.strip():
            cleaned = _strip_html(content)
            if cleaned:
                body_parts.append(f"{heading}\n\n{cleaned}")

    body = "\n\n".join(body_parts)

    # ── 组合完整文件内容 ──
    lines = ["---"]
    for key, val in frontmatter.items():
        lines.append(f"{key}: {val}")
    lines.append("---")
    lines.append("")
    lines.append(f"# {clean_title}")
    lines.append("")
    lines.append(body)

    file_content = "\n".join(lines)

    # ── 生成文件名 ──
    # 截取标题前 30 个字符作为文件名
    safe_title = clean_title[:60].strip()
    safe_title = re.sub(r'[\\/:*?"<>|]', "", safe_title)
    filename = f"{prefix}{case_number_int}号 {safe_title}.md"

    # ── IP 分类 ──
    target_dir = DEST_DIR / subdir
    staging_path = STAGING_DIR / filename

    # ── 写入 staging ──
    try:
        STAGING_DIR.mkdir(parents=True, exist_ok=True)
        with open(str(staging_path), "w", encoding="utf-8", newline="\n") as f:
            f.write(file_content)
        log(f"  ✅ {filename} → {subdir}/")
    except OSError as e:
        log(f"  ❌ 写入失败 {filename}: {e}")
        return None

    return {
        "case_id": case_id,
        "case_number": case_number,
        "judgment_date": judgment_date,
        "category": subdir,
    }


# ── 主流程 ────────────────────────────────────────────────────────


async def main() -> int:
    """主入口。

    Returns:
        0 成功 / 1 失败
    """
    start_time = time.time()
    log("=" * 60)
    log("案例数据库自动导入 — 开始")
    log(f"日期: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 60)

    # ── 0. 网络自检（防 VPN/代理干扰静默失败） ──
    log("[0/5] 网络自检")
    net_ok, net_msg = await check_network()
    if not net_ok:
        log(f"❌ 网络异常，终止：{net_msg}")
        log("   ⚠️ 疑似 VPN/代理干扰——已确认 VPN 会导致 rmfyalk TLS 连接失败（SSL EOF/RST）。请关闭 VPN 后重跑。")
        write_cron_status(
            "network_error",
            f"网络自检失败：{net_msg}（疑似 VPN/代理干扰）",
            error_type="network",
            duration_sec=time.time() - start_time,
        )
        return 1
    log(f"✅ {net_msg}")

    # ── 1. 确保 token 有效 ──
    log("[1/5] Token 检查")
    if not ensure_token():
        log("❌ Token 不可用，终止")
        write_cron_status(
            "failed",
            "Token 不可用，自动登录失败（请检查 VPN 是否关闭 + .env 账密是否正确）",
            error_type="token",
            duration_sec=time.time() - start_time,
        )
        return 1

    # ── 2. 初始化 client ──
    try:
        from client import client as rmfyalk_client
    except ImportError as e:
        log(f"❌ 导入 client.py 失败: {e}")
        return 1

    # ── 3. 执行 11 个检索任务 ──
    log("[2/5] 执行检索任务")
    # 启动时随机延迟 0-10 秒，避免规律性被识别
    import random as _random
    start_delay = _random.uniform(0, 10)
    if start_delay > 1:
        log(f"  防爬冷启动: 等待 {start_delay:.0f} 秒")
        await asyncio.sleep(start_delay)

    all_results: list[dict] = []
    for sort_id, label in SEARCH_TASKS:
        items = await search_task(rmfyalk_client, sort_id, label)
        all_results.extend(items)
        # 任务间随机延迟 0.5-2 秒
        await asyncio.sleep(_random.uniform(0.5, 2.0))

    # ── 关键词兜底检索（覆盖边缘 IP 类型） ──
    log("  关键词兜底检索...")
    for keyword, label, sf in KEYWORD_FALLBACKS:
        items = await search_keyword_fallback(rmfyalk_client, keyword, label, sf)
        all_results.extend(items)
        await asyncio.sleep(_random.uniform(0.5, 1.5))

    log(f"    合并后共 {len(all_results)} 条结果")

    if not all_results:
        log("⚠️ 未检索到任何案例，cron 结束")
        write_cron_status(
            "failed",
            "未检索到任何案例（API 异常或 sort_id 失效，需人工核查）",
            error_type="search",
            duration_sec=time.time() - start_time,
        )
        return 0

    # ── 4. 去重 ──
    log("[3/5] 去重")
    processed_ids = load_processed_ids()
    new_cases, skipped = dedup(all_results, processed_ids)
    log(f"    新增: {len(new_cases)} 篇")
    log(f"    跳过: {len(skipped)} 篇（已存在）")

    if not new_cases:
        log("✅ 无新增案例，cron 完成")
        write_cron_status(
            "success",
            "无新增案例（全部已去重）",
            duration_sec=time.time() - start_time,
            search_total=len(all_results),
            skipped=len(skipped),
        )
        return 0

    # ── 5. 逐个导出 ──
    log("[4/5] 导出案例")
    exported: list[dict] = []
    processed_list: list[dict] = []

    # 先加载已有 processed 列表（用于追加）
    if PROCESSED_JSON.exists():
        try:
            with open(str(PROCESSED_JSON), "r", encoding="utf-8") as f:
                processed_list = json.load(f)
        except (json.JSONDecodeError, OSError):
            processed_list = []

    for i, item in enumerate(new_cases, 1):
        log(f"  导出 {i}/{len(new_cases)}...")
        result = await export_case(rmfyalk_client, item)
        if result:
            exported.append(result)
            processed_list.append(result)
            processed_ids.add(result["case_id"])
        # 导出间随机延迟 1-3 秒（详情接口频率限制更敏感）
        await asyncio.sleep(_random.uniform(1.0, 3.0))

    # ── 6. 保存 processed_ids ──
    log("[5/5] 更新缓存")
    save_processed_ids(processed_list)

    # ── 完成 ──
    log("=" * 60)
    log(f"🎉 完成！")
    log(f"  检索任务: {len(SEARCH_TASKS)} 个")
    log(f"  总结果: {len(all_results)} 条")
    log(f"  新增导出: {len(exported)} 篇")
    log(f"  去重跳过: {len(skipped)} 篇")
    log(f"  staging: {STAGING_DIR}")
    log("=" * 60)

    write_cron_status(
        "success",
        "导入完成",
        duration_sec=time.time() - start_time,
        search_total=len(all_results),
        exported=len(exported),
        skipped=len(skipped),
    )
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
