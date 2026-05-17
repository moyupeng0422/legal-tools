"""国家法律法规数据库 MCP Server"""

from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

from client import client, ApiError
from models import (
    FlkSearchInput, FlkDetailInput, FlkHitDisplayInput, FlkEnumInput,
    FlkSuggestInput, FlkRelatedInput, FlkDownloadInput, FlkExportInput,
    FlkHighSearchInput, FlkHighHitDisplayInput, FlkHighXgzlInput,
)
from formatters import (
    format_search_results, format_law_detail, format_hit_display,
    format_enum_data, format_suggestions, format_related, format_download,
    format_high_search_results, format_high_xgzl,
)

mcp = FastMCP("flk_npc_mcp", host="127.0.0.1", port=18062)

DEFAULT_EXPORT_DIR = os.environ.get("EXPORT_DIR", "")


def _handle_error(e: Exception) -> str:
    if isinstance(e, ApiError):
        return f"API 错误: {e}"
    if "SSL" in str(e) or "Certificate" in str(e):
        return f"网络错误: {e}"
    if "Timeout" in str(e):
        return f"请求超时: {e}"
    return f"错误: {type(e).__name__}: {e}"


@mcp.tool(
    name="flk_search",
    annotations={
        "title": "搜索法律法规",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def search(params: FlkSearchInput) -> str:
    """搜索国家法律法规数据库中的法律、行政法规、部门规章、司法解释等。

    支持标题搜索和全文搜索，可按分类、制定机关、年份、时效性等条件过滤。
    搜索结果中包含法律法规 ID（bbbs），可用于 flk_get_detail 和 flk_hit_display。

    Args:
        params: 搜索参数。search_content 为关键词，search_range 控制搜索范围（1=标题, 2=全文）。

    Returns:
        Markdown 格式的搜索结果列表，含 ID、标题、状态、制定机关等信息。
    """
    try:
        body = {
            "searchContent": params.search_content,
            "searchType": params.search_type,
            "searchRange": params.search_range,
            "flfgCodeId": params.flfg_code_id,
            "zdjgCodeId": params.zdjg_code_id,
            "gbrqYear": params.gbrq_year,
            "sxx": [params.sxx] if params.sxx is not None else [],
            "orderByParam": {"order": "", "sort": ""},
            "pageNum": params.page_num,
            "pageSize": params.page_size,
        }
        result = await client.post("search/list", body)
        return format_search_results(result)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="flk_get_detail",
    annotations={
        "title": "获取法律法规详情",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def get_detail(params: FlkDetailInput) -> str:
    """获取法律法规完整详情，包括元数据、目录结构树、历史版本和相关文件。

    使用搜索结果中的 bbbs 字段作为法律法规 ID。

    Args:
        params: 包含 bbbs（必填，法律法规 ID）。

    Returns:
        Markdown 格式的法律法规详情，含完整的章节/条文目录树。
    """
    try:
        result = await client.get(f"search/flfgDetails?bbbs={params.bbbs}")
        data = result.get("data", {})
        return format_law_detail(data)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="flk_hit_display",
    annotations={
        "title": "命中展示",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def hit_display(params: FlkHitDisplayInput) -> str:
    """获取指定法律法规中关键词命中的法条片段。

    返回包含搜索关键词的具体条文片段，关键词以加粗显示。
    这是定位具体适用法条的核心工具。

    Args:
        params: bbbs 为法律法规 ID，search_content 为搜索关键词。

    Returns:
        Markdown 格式的命中法条片段列表。
    """
    try:
        body = {
            "bbbs": params.bbbs,
            "searchContent": params.search_content,
            "searchType": params.search_type,
            "searchRange": params.search_range,
        }
        result = await client.post("search/hitDisplay", body)
        data = result.get("data", {})
        return format_hit_display(data, params.search_content)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="flk_get_enum",
    annotations={
        "title": "获取分类枚举",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def get_enum(params: FlkEnumInput) -> str:
    """查询法律法规分类树或制定机关分类树。

    获取到的代码(id)可用于 flk_search 的 flfg_code_id 或 zdjg_code_id 参数。

    Args:
        params: category 为分类类型，flfgfl=法律分类, zdjgfl=制定机关。

    Returns:
        Markdown 格式的分类树，含 ID 和名称。
    """
    try:
        result = await client.get("search/enumData")
        data = result.get("data", {})
        category_data = data.get(params.category, {})
        return format_enum_data(category_data, params.category)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="flk_search_suggest",
    annotations={
        "title": "搜索建议",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def search_suggest(params: FlkSuggestInput) -> str:
    """获取搜索关键词的自动补全建议。

    Args:
        params: title 为搜索关键词前缀。

    Returns:
        建议列表。
    """
    try:
        result = await client.get(f"prompts/search?title={params.title}")
        return format_suggestions(result.get("data"))
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="flk_get_related",
    annotations={
        "title": "获取相关法律法规",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def get_related(params: FlkRelatedInput) -> str:
    """获取与指定法律法规相关的其他法规推荐。

    Args:
        params: bbbs 为法律法规 ID。

    Returns:
        相关法律法规列表。
    """
    try:
        result = await client.get(f"search/recommend?bbbs={params.bbbs}")
        return format_related(result.get("data"))
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="flk_download",
    annotations={
        "title": "获取下载链接",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def download(params: FlkDownloadInput) -> str:
    """获取法律法规文件的下载链接（docx 或 word 格式）。

    Args:
        params: bbbs 为法律法规 ID，file_type 为文件类型（默认 docx）。

    Returns:
        下载链接信息。
    """
    try:
        result = await client.get(
            f"download/pc?bbbs={params.bbbs}&fileType={params.file_type}"
        )
        return format_download(result.get("data", {}))
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="flk_high_search",
    annotations={
        "title": "高级检索法律法规",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def high_search(params: FlkHighSearchInput) -> str:
    """多条件组合搜索法律法规。支持 9 个字段自由组合，每个条件可设置精确/模糊和并且/或者/不含逻辑。

    适用场景：普通搜索无法满足时，需要多字段交叉过滤、或需要搜索相关资料内容时使用。

    支持字段：title(法律标题)、content(法律全文)、xgzl.title(相关资料标题)、xgzl.content(相关资料全文)、
    gbrq(公布日期,需传['起始','结束'])、sxrq(施行日期)、flfg_code_id(法律分类代码)、zdjg_code_id(制定机关代码)、sxx(时效性代码)。

    示例：
    - 查找标题含"专利"且全文含"侵权"的法规: conditions=[{field_name:"title",values:["专利"]},{field_name:"content",values:["侵权"],search_type:1}]
    - 查找生效中的商标相关法规: conditions=[{field_name:"title",values:["商标"]},{field_name:"sxx",values:[3]}]

    Args:
        params: 高级检索参数，conditions 为条件列表。

    Returns:
        Markdown 格式的搜索结果，含 ID、标题、状态等。
    """
    try:
        api_body = params.to_api_dict()
        result = await client.post("highSearch/highSearch", api_body)
        return format_high_search_results(result, api_body["dataList"])
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="flk_high_hit_display",
    annotations={
        "title": "高级检索命中展示",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def high_hit_display(params: FlkHighHitDisplayInput) -> str:
    """获取高级检索结果中指定法律法规的命中法条片段。

    需传入与 flk_high_search 相同的条件列表，返回匹配所有条件的法条片段。

    Args:
        params: bbbs 为法律法规 ID，conditions 为搜索条件列表。

    Returns:
        Markdown 格式的命中法条片段列表。
    """
    try:
        api_body = params.to_api_dict()
        result = await client.post("highSearch/hitDisplay", api_body)
        data = result.get("data", {})
        keywords = "; ".join(
            str(v) for c in params.conditions for v in c.values
        )
        return format_hit_display(data, keywords)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="flk_high_xgzl",
    annotations={
        "title": "高级检索相关资料",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def high_xgzl(params: FlkHighXgzlInput) -> str:
    """获取高级检索结果中指定法律法规的相关资料（如修改决定、实施细则等）。

    Args:
        params: bbbs 为法律法规 ID，conditions 为搜索条件列表。

    Returns:
        Markdown 格式的相关资料列表。
    """
    try:
        api_body = params.to_api_dict()
        result = await client.post("highSearch/xgzl", api_body)
        data = result.get("data", {})
        return format_high_xgzl(data)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="flk_export_law",
    annotations={
        "title": "导出到 Obsidian",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def export_law(params: FlkExportInput) -> str:
    """将法律法规导出为 Obsidian 格式并写入法律法规数据库。

    支持单条导出（传入 bbbs）和批量导出（传入 search_content 按关键词搜索后导出）。
    自动完成：分类识别 → 确定目标目录 → 生成 frontmatter + body → 写入文件。
    dry_run=True 时只返回内容不写文件，用于预览。

    Args:
        params: 导出参数。bbbs 或 search_content 至少提供一个。

    Returns:
        导出结果汇总或预览内容。
    """
    import asyncio
    from collections import Counter
    from export_formatter import format_obsidian_law

    try:
        output_dir = params.target_dir or DEFAULT_EXPORT_DIR

        if params.dry_run:
            return await _export_preview(params, output_dir)
        return await _export_write(params, output_dir)
    except Exception as e:
        return _handle_error(e)


async def _export_preview(params: FlkExportInput, output_dir: str) -> str:
    from export_formatter import format_obsidian_law

    if params.bbbs:
        result = await client.get(f"search/flfgDetails?bbbs={params.bbbs}")
        data = result.get("data", {})
        if not data:
            return "未获取到法律法规详情。"
        file_content, filename, subdir = format_obsidian_law(data)
        return f"## 预览导出结果\n\n**目标路径**: `{subdir}/{filename}`\n\n---\n\n{file_content}"

    # 批量预览
    body = {
        "searchContent": params.search_content or "",
        "searchType": 2,
        "searchRange": params.search_range,
        "sxx": [params.sxx] if params.sxx is not None else [],
        "orderByParam": {"order": "", "sort": ""},
        "pageNum": 1,
        "pageSize": min(params.max_results, 20),
    }
    result = await client.post("search/list", body)
    rows = result.get("rows", [])
    total = result.get("total", 0)

    if not rows:
        return "未检索到匹配的法律法规。"

    lines = [f"## 批量预览（共 {total} 条，显示前 {len(rows)} 条）\n"]
    for i, row in enumerate(rows, 1):
        title = row.get("title", "")
        from formatters import clean_highlight
        clean = clean_highlight(title)
        lines.append(f"{i}. **{clean}** (`{row.get('bbbs', '')}`)")

    lines.append(f"\n> 实际导出时将获取每条法规的完整详情。")
    return "\n".join(lines)


async def _export_write(params: FlkExportInput, output_dir: str) -> str:
    import asyncio
    from collections import Counter
    from export_formatter import format_obsidian_law

    ip_counter = Counter()
    exported = 0
    skipped = 0
    failed = 0
    file_list = []

    if params.bbbs:
        result = await client.get(f"search/flfgDetails?bbbs={params.bbbs}")
        data = result.get("data", {})
        if not data:
            return "未获取到法律法规详情。"

        file_content, filename, subdir = format_obsidian_law(data)
        target_path = os.path.join(output_dir, subdir, filename)

        if os.path.exists(target_path):
            return f"文件已存在，跳过: `{subdir}/{filename}`"

        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(file_content)

        return f"导出成功！\n文件: `{subdir}/{filename}`"

    # 批量导出
    items = []
    page = 1
    while len(items) < params.max_results:
        body = {
            "searchContent": params.search_content or "",
            "searchType": 2,
            "searchRange": params.search_range,
            "sxx": [params.sxx] if params.sxx is not None else [],
            "orderByParam": {"order": "", "sort": ""},
            "pageNum": page,
            "pageSize": 20,
        }
        result = await client.post("search/list", body)
        rows = result.get("rows", [])
        if not rows:
            break
        items.extend(rows)
        if len(items) >= result.get("total", 0):
            break
        page += 1

    items = items[:params.max_results]
    if not items:
        return "未检索到匹配的法律法规。"

    for i, item in enumerate(items, 1):
        bbbs = item.get("bbbs", "")
        try:
            detail_result = await client.get(f"search/flfgDetails?bbbs={bbbs}")
            data = detail_result.get("data", {})
            if not data:
                failed += 1
                continue

            file_content, filename, subdir = format_obsidian_law(data)
            target_path = os.path.join(output_dir, subdir, filename)

            if os.path.exists(target_path):
                skipped += 1
                continue

            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(file_content)

            file_list.append(f"{subdir}/{filename}")
            exported += 1
        except Exception:
            failed += 1

        if i < len(items):
            await asyncio.sleep(0.5)

    lines = ["导出完成！\n"]
    lines.append(f"总计: {len(items)} 条")
    lines.append(f"导出: {exported} 条")
    if skipped:
        lines.append(f"跳过（已存在）: {skipped} 条")
    if failed:
        lines.append(f"失败: {failed} 条")

    if file_list:
        lines.append("\n文件列表:")
        for j, fp in enumerate(file_list, 1):
            lines.append(f"{j}. `{fp}`")

    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
