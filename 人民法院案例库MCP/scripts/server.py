"""人民法院案例库 MCP Server"""

from __future__ import annotations

import base64
import json
import sys

from mcp.server.fastmcp import FastMCP

from client import client, TokenExpiredError, ApiError
from models import SearchInput, CaseDetailInput, StatisticsInput, SetTokenInput, EnumInput, ExportInput
from formatters import format_search_results, format_case_detail, format_statistics

mcp = FastMCP("rmfyalk_mcp", host="127.0.0.1", port=18061)

# XML 文件名映射：field 参数 → XML 文件名
ENUM_XML_MAP = {
    "sort": "cpal_sort_new1_id.xml",
    "case_sort": "cpal_casesort_id.xml",
    "court_level": "cpws_fyjb_id.xml",
    "trial_procedure": "cpal_slcx_id.xml",
    "court": "cpal_fcourt_id.xml",
    "doc_type": "cpal_wsxz_id.xml",
}


def _handle_error(e: Exception) -> str:
    if isinstance(e, TokenExpiredError):
        return f"认证错误: {e}\n请先使用 rmfyalk_set_token 工具设置有效的 Token。"
    if isinstance(e, ApiError):
        return f"API 错误: {e}"
    if "401" in str(e):
        return "认证失败：Token 无效或已过期。请使用 rmfyalk_set_token 更新 Token。"
    if "SSL" in str(e) or "Certificate" in str(e):
        return f"网络错误: {e}"
    return f"错误: {type(e).__name__}: {e}"


@mcp.tool(
    name="rmfyalk_search",
    annotations={
        "title": "搜索人民法院案例",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def search(params: SearchInput) -> str:
    """搜索人民法院案例库中的指导性案例和参考案例。

    支持多种检索方式，所有高级检索字段之间为 AND 关系（同时满足）：
    - 关键词检索：keyword（一般检索）或 key_title/key_content/keyword_tag（高级检索文本字段）
    - 下拉字段检索：sort_id(案由)、case_sort(案件类型)、court_level(法院级别)、
      trial_procedure(审理程序)、court(审理法院)、doc_type(文书类型)
    - 精确字段：case_number(案例编号)、case_ref(案号)

    下拉字段的分类代码可通过 rmfyalk_get_enum 工具查询。

    Args:
        params: 搜索参数。keyword 或任意高级检索字段至少提供一个。

    Returns:
        Markdown 格式的搜索结果列表。
    """
    try:
        body = client.build_search_body(
            keyword=params.keyword,
            search_field=params.search_field,
            case_type=params.case_type,
            match_type=params.match_type,
            page=params.page,
            page_size=params.page_size,
            sort_field=params.sort_field,
            key_title=params.key_title,
            key_content=params.key_content,
            case_number=params.case_number,
            case_ref=params.case_ref,
            keyword_tag=params.keyword_tag,
            sort_id=params.sort_id,
            case_sort=params.case_sort,
            court_level=params.court_level,
            trial_procedure=params.trial_procedure,
            court=params.court,
            doc_type=params.doc_type,
        )
        result = await client.post("cpwsAl/search", body)
        return format_search_results(result.get("data", {}))
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="rmfyalk_get_case",
    annotations={
        "title": "获取案例详情",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def get_case(params: CaseDetailInput) -> str:
    """获取案例完整详情，包括裁判要点、基本案情、裁判结果、裁判理由和关联法条。

    使用搜索结果中的 cpws_al_id 字段值作为 case_id 参数。

    Args:
        params: 包含 case_id（必填，搜索结果中的 cpws_al_id）和可选的 sections 列表。

    Returns:
        Markdown 格式的案例详情，含完整裁判文书内容。
    """
    try:
        result = await client.post("cpwsAl/content", {"gid": params.case_id})
        case_data = result.get("data", {})
        return format_case_detail(case_data, params.sections)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="rmfyalk_get_statistics",
    annotations={
        "title": "获取案例统计信息",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def get_statistics(params: StatisticsInput) -> str:
    """获取案例库统计信息，包括案例类型分布、关键词聚类和年份分布。

    可选传入关键词获取特定搜索结果的统计数据。

    Args:
        params: 统计参数，keyword 可选。

    Returns:
        Markdown 格式的统计报告。
    """
    try:
        base_body = None
        if params.keyword:
            base_body = {
                "page": 1, "size": 1, "lib": "qb",
                "searchParams": {
                    "userSearchType": 1, "isAdvSearch": "0",
                    "selectValue": ["qw"], "lib": "cpwsAl_qb",
                    "sort_field": "", "keyTitle": [params.keyword],
                },
            }

        type_body = base_body or {
            "page": 1, "size": 1, "lib": "qb",
            "searchParams": {
                "userSearchType": 1, "isAdvSearch": "0",
                "selectValue": ["qw"], "lib": "cpwsAl_qb",
                "sort_field": "", "keyTitle": [""],
            },
        }

        total_result = await client.post("cpwsAl/cpwsAlTypeNextLeftCluster", type_body)

        keyword_data = None
        year_data = None
        if base_body:
            try:
                kw_result = await client.post("cpwsAl/keywordNextLeftCluster", {**base_body, "pdh": 1})
                keyword_data = kw_result.get("data", [])
            except Exception:
                pass
            try:
                yr_result = await client.post("cpwsAl/yearNextLeftCluster", {**base_body, "pdh": 1})
                year_data = yr_result.get("data", [])
            except Exception:
                pass

        return format_statistics(total_result, keyword_data, year_data)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="rmfyalk_get_enum",
    annotations={
        "title": "获取分类枚举代码",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def get_enum(params: EnumInput) -> str:
    """查询高级检索下拉字段的分类代码。

    支持 6 个下拉字段，返回指定父节点下的子分类列表。
    获取到的代码(id)可用于 rmfyalk_search 的对应参数。

    字段说明：
    - sort: 案由/罪名（有层级树结构）
    - case_sort: 案件类型（01刑事~06调解，无子节点）
    - court_level: 法院级别（01最高~05专门，无子节点）
    - trial_procedure: 审理程序（01一审~04其他，04有子节点）
    - court: 审理法院（34个省级节点，均有子节点）
    - doc_type: 文书类型（001判决书~06通知书，无子节点）

    Args:
        params: field 为字段名，parent_id 为可选的父节点 ID。

    Returns:
        Markdown 格式的分类代码列表。
    """
    try:
        xml_name = ENUM_XML_MAP.get(params.field)
        if not xml_name:
            valid = ", ".join(ENUM_XML_MAP.keys())
            return f"未知字段 '{params.field}'。支持的字段: {valid}"

        import httpx as _httpx

        url = "https://rmfyalk.court.gov.cn/cpws_al_api/api/common/getXmlToTree"
        query = f"xmlName={xml_name}"
        if params.parent_id:
            query += f"&nodeId={params.parent_id}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "faxin-cpws-al-token": client.token,
        }

        async with _httpx.AsyncClient(verify=False, timeout=15) as _c:
            resp = await _c.get(f"{url}?{query}", headers=headers)

        data = resp.json()
        if data.get("code") != 0:
            return f"获取失败: {data.get('msg', '未知错误')}"

        nodes = data.get("data", [])
        if not nodes:
            return "该节点下无子分类。"

        field_names = {
            "sort": "案由/罪名", "case_sort": "案件类型", "court_level": "法院级别",
            "trial_procedure": "审理程序", "court": "审理法院", "doc_type": "文书类型",
        }
        lines = [f"## {field_names.get(params.field, params.field)}\n"]
        lines.append(f"共 {len(nodes)} 个选项:\n")
        for node in nodes:
            leaf = "" if node.get("last") else " → 有子节点，用 parent_id={node['id']} 展开"
            lines.append(f"- `{node['id']}` — {node['title']}{leaf}")

        return "\n".join(lines)
    except Exception as e:
        return _handle_error(e)


DEFAULT_EXPORT_DIR = os.environ.get("EXPORT_DIR", "")


@mcp.tool(
    name="rmfyalk_export_case",
    annotations={
        "title": "导出案例到 Obsidian",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def export_case(params: ExportInput) -> str:
    """将人民法院案例库案例导出为 Obsidian 格式并写入司法案例数据库。

    支持两种模式：
    - 单条导出：传入 case_id（搜索结果中的 cpws_al_id）
    - 批量导出：传入 keyword 或 sort_id，自动搜索并逐条导出

    自动完成：IP类型分类 → 确定目标目录 → 生成 frontmatter + body → 写入文件。
    dry_run=True 时只返回内容不写文件，用于预览。

    Args:
        params: 导出参数。case_id 或 (keyword/sort_id) 至少提供一个。

    Returns:
        导出结果汇总或预览内容。
    """
    import asyncio
    from collections import Counter
    from export_formatter import format_obsidian_case

    try:
        if params.dry_run:
            return await _export_preview(params)
        return await _export_write(params)
    except Exception as e:
        return _handle_error(e)


async def _export_preview(params: ExportInput) -> str:
    """dry-run 模式：只返回格式化内容不写文件"""
    from export_formatter import format_obsidian_case

    if params.case_id:
        # 单条预览
        result = await client.post("cpwsAl/content", {"gid": params.case_id})
        case_data = result.get("data", {}).get("data", {})
        if not case_data:
            return "未获取到案例详情。"
        file_content, filename, subdirectory = format_obsidian_case(case_data)
        return f"## 预览导出结果\n\n**目标路径**: `{subdirectory}/{filename}`\n\n---\n\n{file_content}"

    # 批量预览
    body = client.build_search_body(
        keyword=params.keyword or "",
        case_type=params.case_type,
        page=1,
        page_size=50,
        sort_id=params.sort_id,
    )
    result = await client.post("cpwsAl/search", body)
    data = result.get("data", {})
    items = data.get("datas", [])
    total = data.get("totalCount", 0)

    if not items:
        return "未检索到匹配的案例。"

    lines = [f"## 批量预览（共 {total} 条，显示前 {len(items)} 条）\n"]

    for i, item in enumerate(items, 1):
        title = item.get("cpws_al_title", "")
        case_type_label = "指导性案例" if item.get("cpws_al_type") == "01" else "参考案例"
        sort_name = item.get("cpws_al_sort_name", "")
        cpyz = item.get("cpws_al_cpyz", "")

        # 快速分类
        from formatters import html_to_text
        classify_text = f"{sort_name} {title} {html_to_text(cpyz)}"
        from export_formatter import classify_ip_type
        ip_type, subdir = classify_ip_type(classify_text)

        lines.append(f"{i}. **{title}** → `{subdir}/` ({ip_type})")

    lines.append(f"\n> 实际导出时将获取每条案例的完整详情。")
    return "\n".join(lines)


async def _export_write(params: ExportInput) -> str:
    """实际写入文件模式"""
    import asyncio
    import os
    from collections import Counter
    from export_formatter import format_obsidian_case

    output_dir = params.target_dir or DEFAULT_EXPORT_DIR
    ip_counter = Counter()
    exported = 0
    skipped = 0
    failed = 0
    file_list = []

    if params.case_id:
        # 单条导出
        result = await client.post("cpwsAl/content", {"gid": params.case_id})
        case_data = result.get("data", {}).get("data", {})
        if not case_data:
            return "未获取到案例详情。"

        file_content, filename, subdirectory = format_obsidian_case(case_data)
        target_path = os.path.join(output_dir, subdirectory, filename)

        if os.path.exists(target_path):
            return f"文件已存在，跳过: `{subdirectory}/{filename}`"

        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(file_content)

        import re
        ip_m = re.search(r'IP类型: "([^"]+)"', file_content)
        ip_type = ip_m.group(1) if ip_m else "综合"
        return f"✅ 导出成功！\n文件: `{subdirectory}/{filename}`\nIP类型: {ip_type}"

    # 批量导出
    items = []
    page = 1
    while True:
        body = client.build_search_body(
            keyword=params.keyword or "",
            case_type=params.case_type,
            page=page,
            page_size=20,
            sort_id=params.sort_id,
        )
        result = await client.post("cpwsAl/search", body)
        data = result.get("data", {})
        page_items = data.get("datas", [])
        total = data.get("totalCount", 0)
        if not page_items:
            break
        items.extend(page_items)
        if len(items) >= total:
            break
        page += 1

    if not items:
        return "未检索到匹配的案例。"

    for i, item in enumerate(items, 1):
        case_id = item.get("cpws_al_id", "")
        try:
            detail_result = await client.post("cpwsAl/content", {"gid": case_id})
            case_data = detail_result.get("data", {}).get("data", {})
            if not case_data:
                failed += 1
                continue

            file_content, filename, subdirectory = format_obsidian_case(case_data)
            target_path = os.path.join(output_dir, subdirectory, filename)

            if os.path.exists(target_path):
                skipped += 1
                continue

            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(file_content)

            import re
            ip_m = re.search(r'IP类型: "([^"]+)"', file_content)
            ip_counter[ip_m.group(1) if ip_m else "综合"] += 1
            file_list.append(f"{subdirectory}/{filename}")
            exported += 1
        except Exception:
            failed += 1

        if i < len(items):
            await asyncio.sleep(0.5)

    lines = ["导出完成！\n"]
    lines.append(f"总计: {len(items)} 条")
    for ip_type, count in ip_counter.most_common():
        lines.append(f"- {ip_type}: {count} 条")
    if skipped:
        lines.append(f"跳过（已存在）: {skipped} 条")
    if failed:
        lines.append(f"失败: {failed} 条")

    if file_list:
        lines.append("\n文件列表:")
        for j, fp in enumerate(file_list, 1):
            lines.append(f"{j}. `{fp}`")

    return "\n".join(lines)


@mcp.tool(
    name="rmfyalk_set_token",
    annotations={
        "title": "设置认证 Token",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def set_token(params: SetTokenInput) -> str:
    """设置或更新人民法院案例库的认证 Token。

    从浏览器 Cookie 中获取 faxin-cpws-al-token 的值传入。Token 有效期约 4 小时。
    设置后会自动验证 Token 有效性并返回用户信息。

    Args:
        params: 包含 token 字符串。

    Returns:
        Token 设置结果和用户身份信息。
    """
    try:
        client.set_token(params.token)
        result = await client.post("user/getUserInfo", {"state": ""})
        user_data = result.get("data", {})
        phone = user_data.get("phone", "") or user_data.get("userId", "")
        if phone and len(phone) > 4:
            phone = phone[:3] + "****" + phone[-4:]

        exp_info = ""
        try:
            parts = params.token.split(".")
            if len(parts) == 3:
                payload = parts[1] + "=" * (4 - len(parts[1]) % 4)
                decoded = json.loads(base64.urlsafe_b64decode(payload))
                import time
                exp_ts = decoded.get("exp", 0)
                if exp_ts:
                    remaining = exp_ts - time.time()
                    if remaining > 0:
                        exp_info = f"\nToken 有效期剩余: 约 {int(remaining / 3600)} 小时 {int((remaining % 3600) / 60)} 分钟"
                    else:
                        exp_info = "\n⚠️ Token 已过期"
        except Exception:
            pass

        return f"Token 设置成功！\n用户ID: {user_data.get('userId', '-')}\n手机号: {phone}{exp_info}"
    except Exception as e:
        client.set_token("")
        return f"Token 设置失败: {e}\n请检查 Token 是否正确，从浏览器 Cookie 中获取 faxin-cpws-al-token 的值。"


@mcp.tool(
    name="rmfyalk_check_token",
    annotations={
        "title": "检查 Token 状态",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def check_token() -> str:
    """检查当前 Token 的有效性和状态。

    Returns:
        Token 状态信息：是否有效、过期时间、用户身份。
    """
    if not client.token:
        return "⚠️ 未设置 Token。请先使用 rmfyalk_set_token 工具设置 Token。\n获取方式：登录 rmfyalk.court.gov.cn → 浏览器开发者工具 → Application → Cookies → 复制 faxin-cpws-al-token 的值。"

    exp_info = ""
    try:
        parts = client.token.split(".")
        if len(parts) == 3:
            payload = parts[1] + "=" * (4 - len(parts[1]) % 4)
            decoded = json.loads(base64.urlsafe_b64decode(payload))
            import time
            exp_ts = decoded.get("exp", 0)
            if exp_ts:
                remaining = exp_ts - time.time()
                if remaining > 0:
                    exp_info = f"有效期剩余: 约 {int(remaining / 3600)} 小时 {int((remaining % 3600) / 60)} 分钟"
                else:
                    exp_info = "⚠️ Token 已过期"
    except Exception:
        pass

    try:
        result = await client.post("user/getUserInfo", {"state": ""})
        user_data = result.get("data", {})
        return f"✅ Token 有效\n用户ID: {user_data.get('userId', '-')}\n{exp_info}"
    except TokenExpiredError:
        return f"❌ Token 已失效\n{exp_info}\n请使用 rmfyalk_set_token 更新 Token。"
    except Exception as e:
        return f"❌ 验证失败: {e}\n{exp_info}"


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
