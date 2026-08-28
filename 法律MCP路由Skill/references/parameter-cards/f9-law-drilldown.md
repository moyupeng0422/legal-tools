# 功能9 · 法条关联资料检索（已知法条 → 案例/期刊/释义/沿革）

> ⚠️ **调用包裹格式（本卡仅法信）**：法信侧工具（faxin_law_tab_detail 等）参数须包一层 `{"params": {...}}`（retest-F1-20260827 建议7）。

> 用户2026-08-04新增：**法信独有**下钻能力——从法条下钻关联资料（案例/裁判规则/期刊/释义/沿革）
> 类型：**分析型**（研究类，多源目标）
> ⚠️ **其他MCP无法条下钻能力，勿用北大法宝/元典绕路**（pitfall #9）
> ⚠️ **法信 Cookie 过期处置（2026-08-26 MCP 工具层修复后）**：检索报"Cookie 已过期"或返回"⚠️ Cookie 疑似过期"（空结果可能为过期态表现，pitfall #43）→ **直接调 `faxin_laws_auto_login` 工具自助刷新**（本卡法信工具均属法规侧 laws server——功能9法信独有，下钻前通常已在前置步骤定位 gid，过期多发生在定位环节，处置同前），刷新后重试本检索；工具刷新失败才按降级规则"标注缺失继续"并上报总skill
> 用途分流：
> - **法条→案例/裁判规则** → 诉讼/类案场景（"商标法57条被怎么判过"）
> - **法条→期刊** → 法律研究/文章写作（E1/E2文献支撑）

---

## ① 法信（免费层·唯一）

### Step 1 — 定位法规与条文
**faxin_law_search(key_title="专利法")** → 获取 gid（如 A294800）

**faxin_law_search_articles(gid, keyword, show_tabs=true)** → 定位条文 + 查看7项tab摘要
```
📎 关联法条:20条 | 释义:✅ | 沿革:✅ | 法律:5 | 裁判规则:31 | 案例:14 | 期刊:29
```

### Step 2 — 下钻关联资料（faxin_law_tab_detail）
| 参数 | 必填 | 说明 | 示例 |
|---|---|---|---|
| gid | ✅ | 法规ID | "A294800" |
| tiao | ✅ | 法条序号（数字字符串） | "53" |
| tab_type | ✅ | 见下表7种 | "link_cases" |
| libid | 否 | 子库ID | — |
| item_gid / item_libid | 否 | **第三层**：link列表中单个条目的gid | — |
| full_content | 否 | true返回完整全文(false=800字符摘要) | false |

**7种 tab_type（第二层·分类列表）**：
| tab_type | 返回内容 | 场景 |
|---|---|---|
| `related` | 关联法条列表 | 法条体系 |
| `interpretation` | 法条释义全文 | 理解条文 |
| `history` | 沿革信息（历次版本对比） | 修订历史（也归功能7） |
| `link_legal` | 法律分类列表 | 关联法律 |
| `link_rules` | **裁判规则列表**（要旨+案件+来源） | 诉讼 |
| `link_cases` | **案例列表**（名称+法院+日期+审级） | 诉讼 |
| `link_journals` | **期刊论文列表**（标题+作者+期刊+期号） | 研究/写作 |

> ✅ **2026-08-13 已修复并验证**：`link_cases`/`link_journals` 曾报"不支持的 tab 类型"——根因是 server.py `_get_tab_detail` link_ 分支循环后漏 return 的代码回归 bug，已修复（补 `return "\n".join(lines_out)`）；**重启 WorkBuddy 后重测全部通过**：link_cases 13222条案例 / link_journals 64条期刊 / 第三层 item_gid 取全文均正常。7 种 tab_type 全部可用。

### Step 3 — 第三层全文（可选）
将第二层条目的 gid 作为 `item_gid` 传入 → 获取完整内容：
- link_legal → 整部法律全文(~17000字)
- link_rules → 裁判规则全文(~6000字)
- link_cases → 案例全文(~19000字)
- link_journals → 期刊论文全文(~35000字)

---

## 推荐工作流

```
诉讼场景："商标法57条被怎么判过"
① faxin_law_search(key_title="商标法") → gid
② faxin_law_search_articles(gid, "侵权", show_tabs=true) → 定位57条+看tab
③ faxin_law_tab_detail(gid, "57", tab_type="link_cases") → 案例列表
   ✅ 2026-08-13修复验证通过（link_cases 13222条）
④ faxin_law_tab_detail(gid, "57", tab_type="link_cases", item_gid=...) → 案例全文
   ✅ 已验证（取某案例/期刊全文正常）

研究场景："该法条的学术文献"
③' faxin_law_tab_detail(gid, tiao, tab_type="link_journals") → 期刊列表
   ✅ 2026-08-13修复验证通过（link_journals 64条）
④' 同上加 item_gid → 期刊论文全文
   ✅ 已验证（如 F802512 张伟君商标法驰名商标保护论文全文）
```

> ⚠️ **历史提示**：link_* 曾报"不支持的 tab 类型"（server.py 漏 return 的代码bug，非功能缺失）——**若再现此报错，先查 server 源码定位根因（代码bug vs 功能缺失）并修复，勿轻信报错判"不支持"**（pitfall #30）。
