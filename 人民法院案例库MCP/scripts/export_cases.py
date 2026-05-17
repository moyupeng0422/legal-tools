"""批量导出人民法院案例库案例到 Obsidian 司法案例数据库"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from collections import Counter

import httpx

# 同目录导入
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
from client import RmfyalkClient, TokenExpiredError, ApiError
from export_formatter import format_obsidian_case, classify_ip_type

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

DEFAULT_OUTPUT_DIR = os.environ.get("EXPORT_DIR", "")


async def fetch_all_cases(
    client: RmfyalkClient,
    keyword: str = "",
    sort_id: str | None = None,
    case_type: str = "guiding",
    page_size: int = 20,
) -> list[dict]:
    """分页获取所有搜索结果"""
    all_items = []
    page = 1

    while True:
        body = client.build_search_body(
            keyword=keyword,
            case_type=case_type,
            page=page,
            page_size=page_size,
            sort_id=sort_id,
        )
        result = await client.post("cpwsAl/search", body)
        data = result.get("data", {})
        items = data.get("datas", [])
        total = data.get("totalCount", 0)

        if not items:
            break

        all_items.extend(items)
        print(f"  第 {page} 页: 获取 {len(items)} 条 (累计 {len(all_items)}/{total})")

        if len(all_items) >= total:
            break
        page += 1

    return all_items


async def fetch_case_detail(client: RmfyalkClient, case_id: str) -> dict | None:
    """获取单条案例详情"""
    try:
        result = await client.post("cpwsAl/content", {"gid": case_id})
        return result.get("data", {}).get("data", {})
    except Exception as e:
        print(f"  ⚠ 获取详情失败 {case_id}: {e}")
        return None


async def export_cases(
    keyword: str = "",
    sort_id: str | None = None,
    case_type: str = "guiding",
    output_dir: str = DEFAULT_OUTPUT_DIR,
    dry_run: bool = False,
    page_size: int = 20,
):
    """主导出流程"""
    # 初始化客户端
    client = RmfyalkClient()
    if not client.token:
        print("❌ 未设置 Token。请在 .env 中设置 RMFYALK_TOKEN 或使用 --token 参数。")
        return

    # 搜索
    search_desc = []
    if keyword:
        search_desc.append(f"关键词='{keyword}'")
    if sort_id:
        search_desc.append(f"案由={sort_id}")
    search_desc.append(f"类型={case_type}")
    print(f"搜索条件: {', '.join(search_desc)}")

    print("\n=== 搜索案例 ===")
    items = await fetch_all_cases(
        client, keyword=keyword, sort_id=sort_id,
        case_type=case_type, page_size=page_size,
    )
    print(f"共获取 {len(items)} 条搜索结果\n")

    if not items:
        print("未找到案例。")
        return

    # 逐条获取详情 + 导出
    print("=== 导出案例 ===")
    ip_counter = Counter()
    exported = 0
    skipped = 0
    failed = 0

    for i, item in enumerate(items, 1):
        case_id = item.get("cpws_al_id", "")
        title = item.get("cpws_al_title", "无标题")
        print(f"[{i}/{len(items)}] {title}")

        # 获取详情
        detail = await fetch_case_detail(client, case_id)
        if not detail:
            failed += 1
            continue

        # 转换格式
        file_content, filename, subdirectory = format_obsidian_case(detail)

        # 确定输出路径
        target_path = os.path.join(output_dir, subdirectory, filename)

        if dry_run:
            ip_type = _get_ip_type_from_content(file_content)
            ip_counter[ip_type] += 1
            print(f"  → {subdirectory}/{filename} ({ip_type})")
        else:
            # 检查文件是否已存在
            if os.path.exists(target_path):
                print(f"  ⏭ 已存在，跳过: {filename}")
                skipped += 1
                continue

            # 确保目录存在
            os.makedirs(os.path.dirname(target_path), exist_ok=True)

            # 写入文件
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(file_content)

            ip_type = _get_ip_type_from_content(file_content)
            ip_counter[ip_type] += 1
            exported += 1
            print(f"  ✓ {subdirectory}/{filename}")

        # 间隔
        if i < len(items):
            await asyncio.sleep(0.5)

    # 汇总
    print(f"\n=== 导出完成 ===")
    action = "预览" if dry_run else "导出"
    print(f"{action}总计: {exported + skipped if not dry_run else exported} 条")
    for ip_type, count in ip_counter.most_common():
        dir_name = _get_dir_for_ip_type(ip_type)
        print(f"  - {ip_type}: {count} 条 → {dir_name}/")
    if skipped:
        print(f"跳过（已存在）: {skipped} 条")
    if failed:
        print(f"失败: {failed} 条")


def _get_ip_type_from_content(content: str) -> str:
    """从文件内容提取 IP 类型"""
    import re
    m = re.search(r'IP类型: "([^"]+)"', content)
    return m.group(1) if m else "综合"


def _get_dir_for_ip_type(ip_type: str) -> str:
    """IP类型 → 目录名"""
    from export_formatter import IP_DIR_MAP
    return IP_DIR_MAP.get(ip_type, DEFAULT_DIR)


def main():
    parser = argparse.ArgumentParser(description="批量导出人民法院案例库案例到 Obsidian")
    parser.add_argument("--token", default="", help="认证 Token（或通过 .env 自动加载）")
    parser.add_argument("--sort-id", default=None, help="案由分类代码，如 20000528")
    parser.add_argument("--keyword", default="", help="搜索关键词")
    parser.add_argument("--case-type", default="guiding", choices=["all", "guiding", "reference"],
                        help="案例类型 (默认: guiding)")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="输出目录")
    parser.add_argument("--dry-run", action="store_true", help="只预览不写文件")
    parser.add_argument("--page-size", type=int, default=20, help="每页条数 (默认: 20)")

    args = parser.parse_args()

    # 如果传了 token，临时写入环境变量
    if args.token:
        os.environ["RMFYALK_TOKEN"] = args.token

    asyncio.run(export_cases(
        keyword=args.keyword,
        sort_id=args.sort_id,
        case_type=args.case_type,
        output_dir=args.output_dir,
        dry_run=args.dry_run,
        page_size=args.page_size,
    ))


if __name__ == "__main__":
    main()
