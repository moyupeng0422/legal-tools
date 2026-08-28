# 功能速查卡索引（parameter-cards）

> 作用：各MCP工具的参数**唯一真相源**——格式写死、LLM不猜。子skill/子agent调用前必须查对应卡。
> 使用方式：按功能编号（功能1-9，见升级表第三节）加载对应卡片；跨功能复用的工具以**本卡为参数标准**。
> 配套：`../upgrade-table.md`（升级路径+计费档位）· `../pitfall-checklist.md`（坑位拦截）· `../scenario-map.md`（场景识别）
> **框架化定位（2026-08-21，2026-08-28 扩展）**：本索引与各卡 = **已知9 MCP 知识库**。①卡内工具是否可用以 `../../data/user-profile.json` 的 mcp_inventory 为准（未启用/不在线自动跳过）②企查查法律数据 10 个工具的完整 schema 统一见 `qcc-legal.md`，f1-f8 只保留路由指针 ③知识库外的 MCP 走通用模式——读该工具的 tool description 定参数，不猜格式 ④profile.path_order_overrides 非空时，卡内"按升级顺序"被该功能覆盖序取代（仅调序，红线不豁免，见 onboarding-guide 附录）。**功能覆盖度兜底**（见升级表 4.0）：某功能在当前 profile 中无可用工具时，标注"本 profile 未覆盖功能N"并继续，不得硬凑。

---

## 一、卡片清单（功能 → 卡片）

| 功能 | 卡片 | 核心工具（按升级顺序） |
|---|---|---|
| 功能1 法条精准查询 | `f1-law-exact.md` | 法信law_search/detail · 企查查article_detail/search · 元典ft_detail · 北大法宝get_law_item_content · 法研iterative · 威科search_law_article · FLK hit_display（仅"法规名+关键词"变体） |
| 功能2 语义找法条 | `f2-semantic-law.md` | FLK拆词 · 法信拆词 · 企查查article_semantic_search · 元典law_vector_search · 北大法宝search_article · 威科search_law |
| 功能3 精准找案例 | `f3-case-exact.md` | RMFYALK case_ref/key_content · 法信case检索 · 企查查case_search/detail · 元典case_details · 北大法宝get_case_list |
| 功能4 语义找案例 | `f4-semantic-case.md` | 法信拆词 · 企查查case_search（关键词拆解） · 元典case_vector_search · 北大法宝search_case · 威科search_case |
| 功能5 类案检索 | `f5-case-search.md` | 法信case_search(20+维度) · 企查查case_search/detail · 北大法宝get_case_list · 元典qwal/ptal |
| 功能6 权威案例 | `f6-authoritative.md` | RMFYALK search · 企查查authoritative_case_search · 元典qwal · 北大法宝get_case_list(caseGrade) |
| 功能7 时效核验/修订历史 | `f7-timeline.md` | 法信沿革 · FLK历史版本 · 企查查法规/条文时效 · 法研status · 北大法宝get_law_list |
| 功能8 引用校验/防幻觉 | `f8-citation.md` | 企查查legal/judicial citation verify · 元典hall_detect(API直调) · 回归功能1/3一般检索 |
| 功能9 法条关联资料 | `f9-law-drilldown.md` | 法信 law_tab_detail（案例/期刊/释义/沿革下钻） |

---

## 二、MCP 总览（9个法律MCP）

| MCP | Server/端口 | 层 | 计费 | 认证 | 工具数 | 卡片涉及 |
|---|---|---|---|---|---|---|
| **法信** | faxin-laws:18063 / faxin-case:18064 | 免费层 | 免费 | Cookie(约1h)过期自动刷新：案例`faxin_wenshu_auto_login`/法规`faxin_laws_auto_login`工具（2026-08-26起，pitfall #29/#43） | 9+6 | f1/f2/f3/f4/f5/f6/f7/f9 |
| **FLK** | flk:18062 | 免费层 | 免费 | 无 | 11 | f2/f7 |
| **RMFYALK** | rmfyalk:18061 | 免费层 | 免费 | Token(4h) | 8 | f3/f6 |
| **北大法宝** | pkulaw-* (9独立server) | 额度层 | 积分25/125分 | API Key | 10 | f1/f2/f3/f4/f5/f6/f7 |
| **元典** | yuandian-law/case/company | 额度层 | 积分1/5/10/15/50分 | API Key | law5+case4+company27 | f1/f2/f3/f4/f5/f6/f7/f8 |
| **法研** | fy-law-search-service | 额度层 | 免费试用500次 | API Key | 2 | f1/f7 |
| **威科** | wk-mcp | 额度层 | 试用10次/工具 | connector | 6 | f1/f2/f4/f7 |
| **企查查法律法规** | qcc-legal-regulation / qcc_legal_regulation | 额度层 | 1分（语义3分） | 企查查 MCP 凭证 | 6 | f1/f2/f7/f8 |
| **企查查司法案例** | qcc-legal-case / qcc_legal_case | 额度层 | 3分 | 企查查 MCP 凭证 | 4 | f3/f4/f5/f6/f8 |

> 企查查企业数据的 6 组 server 不计入“法律 MCP”数量；它们按 `../qcc-enterprise-bridge.md` 作为涉企事实核验桥接入。

---

## 三、跨功能工具归属表（工具主卡位置）

> 同一工具被多个功能引用时，**参数标准以主卡为准**，其他卡片只写指针。

| 工具 | 主卡 | 被引用功能 |
|---|---|---|
| 法信 faxin_law_search | f1 | f7(时效)/f9(定位法规) |
| 法信 faxin_case_search | f5 | f3(案号)/f4(拆词) |
| 北大法宝 get_law_item_content | f1 | f7(时效) |
| 北大法宝 get_case_list | f5 | f3(精确)/f6(caseGrade) |
| 元典 rh_ft_detail | f1 | f7(时效) |
| 元典 rh_ft_search（法条关键词检索） | f2④-2 | f1(🔀变体路径②) |
| FLK flk_hit_display（法规内关键词命中条文） | f1(🔀变体段) | f7(版本锚定组合拳) |
| 威科 search_law_keyword（法规级关键词） | f7⑥ | —（f1 变体排除项，不到条文级） |
| 北大法宝 get_linked_content（文本加超链，125分） | f8备选 | E2文章写作（文本标引） |
| 元典 qwal_search | f6 | f5(类案) |
| 元典 ptal_search | f5 | — |
| RMFYALK search | f6 | f3(案号/标题) |
| 企查查法律数据 10 工具 | qcc-legal | f1-f8（各功能卡只写路径指针） |

> RMFYALK 另有能力（未入卡片主路径）：get_statistics(7维聚合，检索前了解案例分布) / export_case(导出Obsidian) / get_enum(案由/法院代码树，f6已引用)
> 法研仅2个工具（flfg_iterative_search_tool / flfg_parallel_search_tool）——**无全文工具**（CC曾误报flfg_full_text_tool，已撤回）

---

## 四、全局硬规则（所有卡片生效）

1. **北大法宝禁用AGG聚合工具**——一律用独立server工具（参数见各卡）
2. **条号默认传中文**（"第六十五条"），仅北大法宝 get_law_item_content 的 `tiao_num` 传数字（65）
3. **法信/FLK/法研无语义引擎**——法条原生语义用企查查/北大法宝/元典/威科；FLK/法信只做LLM拆词。企查查普通案例搜索不是向量语义，功能4仅作关键词拆解路径
4. **威科10次试用稀缺**——仅功能2关键语义难题用，须用户确认
5. **法研仅法规场景**——免费试用500次内，限功能1/7
6. **元典工具名带 `yuandian_` 前缀**（yuandian_rh_ft_detail），非routeKey
7. **hall_detect 未封装MCP**——功能8防幻觉走 scripts/hall_detect.py 直调HTTP API
8. **法信 Cookie 过期（约1h）→ 调工具自助刷新，不跑本地脚本**——案例侧 `faxin_wenshu_auto_login`、法规侧 `faxin_laws_auto_login`（subprocess 跑 auto_login.py，实测 L2 登录约 39s，成功自动同步凭证）；空结果可能是过期态假空（pitfall #43，server 已加守卫）——所有法信工具统一适用（f5 卡有详版）
9. **调用包裹格式两种口径（2026-08-27 立，2026-08-28 扩展）**——**法信/FLK/RMFYALK 侧工具参数须包一层 `{"params": {...}}`**；**企查查/元典/北大法宝/法研/威科侧参数平铺直传**（不包 params）。子agent 加载 schema 后先对位包裹格式再填参
10. **企查查法律数据同样平铺直传**——不包 `params`；固定最多20条且无分页字段，opaque id 只从搜索/校验结果原样传给同类详情，完整规则见 `qcc-legal.md`
11. **企查查法律库与企业库不得混用**——法规/通用类案不做企业锚定；企业主体事实按 `../qcc-enterprise-bridge.md` 先锚定再最小调用
