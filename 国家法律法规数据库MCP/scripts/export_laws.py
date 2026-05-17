"""批量导出国家法律法规数据库到 Obsidian"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from client import FlkClient
from dotenv import load_dotenv
from export_formatter import format_obsidian_law

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

DEFAULT_OUTPUT_DIR = os.environ.get("EXPORT_DIR", "")


async def fetch_all_cases(
    client: FlkClient,
    search_content: str = "",
    search_range: int = 1,
    sxx: int | None = 3,
    max_results: int = 50,
) -> list[dict]:
    all_items = []
    page = 1

    while len(all_items) < max_results:
        body = {
            "searchContent": search_content,
            "searchType": 2,
            "searchRange": search_range,
            "sxx": sxx,
            "orderByParam": {"order": "", "sort": ""},
            "pageNum": page,
            "pageSize": 20,
        }
        result = await client.post("search/list", body)
        rows = result.get("rows", [])
        total = result.get("total", 0)

        if not rows:
            break

        all_items.extend(rows)
        print(f"  第 {page} 页: 获取 {len(rows)} 条 (累计 {len(all_items)}/{total})")

        if len(all_items) >= total:
            break
        page += 1

    return all_items[:max_results]


async def export_laws(
    search_content: str = "",
    search_range: int = 1,
    sxx: int | None = 3,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    dry_run: bool = False,
    max_results: int = 50,
):
    client = FlkClient()

    search_desc = []
    if search_content:
        search_desc.append(f"关键词='{search_content}'")
    if sxx:
        from formatters import SXX_LABELS
        search_desc.append(f"状态={SXX_LABELS.get(sxx, str(sxx))}")
    print(f"搜索条件: {', '.join(search_desc)}")

    print("\n=== 搜索法律法规 ===")
    items = await fetch_all_cases(
        client, search_content=search_content, search_range=search_range,
        sxx=sxx, max_results=max_results,
    )
    print(f"共获取 {len(items)} 条搜索结果\n")

    if not items:
        print("未找到法律法规。")
        await client.close()
        return

    print("=== 导出法律法规 ===")
    exported = 0
    skipped = 0
    failed = 0

    for i, item in enumerate(items, 1):
        bbbs = item.get("cpws_al_id", item.get("bbbs", ""))
        import re
        title = re.sub(r"<[^>]+>", "", item.get("title", "无标题"))
        print(f"[{i}/{len(items)}] {title}")

        try:
            detail = await client.get(f"search/flfgDetails?bbbs={bbbs}")
            data = detail.get("data", {})
            if not data:
                failed += 1
                continue

            file_content, filename, subdir = format_obsidian_law(data)

            if dry_run:
                print(f"  → {subdir}/{filename}")
            else:
                target_path = os.path.join(output_dir, subdir, filename)
                if os.path.exists(target_path):
                    print(f"  ⏭ 已存在，跳过: {filename}")
                    skipped += 1
                    continue

                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(file_content)
                exported += 1
                print(f"  ✓ {subdir}/{filename}")
        except Exception as e:
            print(f"  ⚠ 失败: {e}")
            failed += 1

        if i < len(items):
            await asyncio.sleep(0.5)

    action = "预览" if dry_run else "导出"
    print(f"\n=== {action}完成 ===")
    print(f"总计: {len(items)} 条")
    print(f"{action}: {exported} 条")
    if skipped:
        print(f"跳过（已存在）: {skipped} 条")
    if failed:
        print(f"失败: {failed} 条")

    await client.close()


def main():
    parser = argparse.ArgumentParser(description="批量导出国家法律法规到 Obsidian")
    parser.add_argument("--search-content", default="", help="搜索关键词")
    parser.add_argument("--search-range", type=int, default=1, choices=[1, 2],
                        help="搜索范围：1=标题, 2=全文（默认标题）")
    parser.add_argument("--sxx", type=int, default=3, choices=[1, 2, 3, 4],
                        help="时效性：1=已废止, 2=被修订, 3=生效中, 4=未生效（默认3）")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="输出目录")
    parser.add_argument("--dry-run", action="store_true", help="只预览不写文件")
    parser.add_argument("--max-results", type=int, default=50, help="最大导出条数（默认50）")

    args = parser.parse_args()
    asyncio.run(export_laws(
        search_content=args.search_content,
        search_range=args.search_range,
        sxx=args.sxx,
        output_dir=args.output_dir,
        dry_run=args.dry_run,
        max_results=args.max_results,
    ))


if __name__ == "__main__":
    main()
