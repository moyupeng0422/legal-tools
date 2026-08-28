# 功能7 · 时效核验 / 修订历史

> ⚠️ **调用包裹格式（本卡涉及：法信·FLK=包裹 / 元典·北大法宝·法研=平铺）**：法信/FLK 侧工具参数须包一层 `{"params": {...}}`；元典/北大法宝/法研侧参数**平铺直传**，不包 params（retest-F1-20260827 建议7）。

> 用户2026-08-04区分两种情况：
> - **仅时效核验**（确认法条现行有效/失效）——除RMFYALK外全部可用
> - **修订历史**（查看历次修改版本）——**仅法信/FLK**
> 类型：**确定型**——确认即止，不强升级
> ⚠️ **法信 Cookie 过期处置（2026-08-26 MCP 工具层修复后）**：检索报"Cookie 已过期"或返回"⚠️ Cookie 疑似过期"（空结果可能为过期态表现，pitfall #43）→ **直接调 `faxin_laws_auto_login` 工具自助刷新**（本卡法信工具均属法规侧 laws server，实测 L2 登录约 39s，成功自动同步凭证），刷新后重试本检索；工具刷新失败才按降级规则"标注缺失继续"并上报总skill

---

## 【仅时效核验】— 确认法条现行有效/失效

> 💡 优先级：先免费层（法信/FLK），命中确认即止，不强升级

### ① 法信（免费层）
**faxin_law_search** — shixiao_id 过滤
| 参数 | 必填 | 说明 | 示例 |
|---|---|---|---|
| key_title | 否* | 标题关键词 | "专利法" |
| shixiao_id | 否 | **01现行有效**/02失效/03已被修改/04尚未生效/05部分失效/06实际失效 | "01" |
| database | 否 | 子库（默认gjfl） | "gjfl" |

**faxin_law_detail** — 返回详情含时效字段；配合 faxin_law_tab_detail(tab_type="history") 看沿革

### ② FLK（免费层·官方）
**flk_search** — sxx 过滤
| 参数 | 必填 | 说明 | 示例 |
|---|---|---|---|
| search_content | ✅ | 关键词 | "专利法" |
| search_range | 否 | 1=标题（默认）/2=全文 | 1 |
| sxx | 否 | **3=生效中**/1=已废止/2=被修订/4=未生效 | 3 |

> ⚠️ **search_type=1 精确匹配（2026-08-27 abtest 实测坑）**：模糊模式（search_type=2）搜"民法典"跑偏返回宪法等无关法规——**定位具体法规一律 `search_type=1` 精确** + search_content 用完整法规名；结果返回后校验标题与预期一致

**flk_get_detail(bbbs)** — 查看 lsyg 历史版本列表（highLight=true为当前版本）

**flk_hit_display(bbbs, search_content)** — 在已定位法规内按关键词**命中法条片段**（免费层"版本锚定+条文定位"组合拳：flk_search 定法规→flk_hit_display 命中具体条文，2026-08-21 D2 真跑验证：一次命中广告法第9/11/17/18/58条，每条附原文）。**参数标准主卡=f1 卡 🔀 变体段（含 search_type 默认值等完整4参数）**
| 参数 | 必填 | 说明 | 示例 |
|---|---|---|---|
| bbbs | ✅ | 法规ID（来自 flk_search 结果） | "ff8081817ab231eb..." |
| search_content | ✅ | 条文关键词 | "绝对化用语" |
| search_range | 否 | 2=全文（命中条文时用；默认1=标题） | 2 |

### ③ 法研（额度层·免费试用500次）
**flfg_iterative_search_tool** — status 过滤
| 参数 | 说明 | 示例 |
|---|---|---|
| query.title | 法规名称 | "中华人民共和国民法典" |
| status | **现行有效**（默认）/尚未生效/已被修改/失效/待核实 | "现行有效" |

### ④ 北大法宝（额度层·25分）
**get_law_item_content(title, tiao_num)** — 返回含 TimelinessDic 时效字段
**get_law_list** — timeliness 数组过滤（实测2026-08-13）
| 参数 | 说明 | 示例 |
|---|---|---|
| title/fulltext | 标题/全文关键词（**空格/逗号=分词AND**） | "专利法" / "盗窃 诈骗" |
| timeliness | 时效数组(**内部OR ✅ 筛选可靠**) | ["现行有效"] |
| effectiveness | 效力位阶数组(OR) | ["法律"] |

> ⚠️ **实测坑位（2026-08-13）**：
> - **effectiveness 筛选有缺陷**：`effectiveness=["法律"]` 时 Total统计生效（188→127）但**返回列表未严格过滤**（混入"地方工作文件"）——**筛选结果须二次校验每条 EffectivenessDic**；timeliness 则可靠无此问题
> - **顿号"、"是字面字符**（连续串匹配，≠分词AND）：`fulltext="盗窃、诈骗"` 只命中连续出现的，结果大幅偏少——多词必须用空格/半角逗号/全角逗号分隔（实测分隔符矩阵：空格=半角逗号=全角逗号=分词AND；顿号=字面串；AND/OR/NOT 英文词仅作词元）
> - 检索法条本体要用"法条原文表述"：`fulltext="盗窃公私财物"`（命中刑法典本体）≠ `fulltext="盗窃罪"`（只命中司法解释/地方文件——法条正文不写罪名）
> - **无翻页**、固定返回20条+Total；排序无规则且不稳定（取最新版须自行按日期排序）

### ⑤ 元典（额度层·1-5分）
**yuandian_rh_ft_detail(fgmc, ftnum)** — 返回含时效性
**yuandian_rh_fg_detail(id/fgmc)** — 法规详情含时效性；**refer_date 支持历史版本查询**（特色，2026-08-15实测完全生效：refer_date=2010-01-01→返回2007原版劳动合同法，条文差异实锤）
**yuandian_rh_fg_search（5分·法规目录查询器）** — 法规**存在性/时效/效力/文号轻量核查**（紧凑元数据一次多条，比④单部全文轻）；独有"纯过滤目录模式"：不传 keyword，`{"xljb_1":"地方性法规","dy":"广东","sxx":"现行有效"}` → 枚举符合条件的法规清单（2026-08-17 指南实测）
> ⚠️ 坑位（pitfall #44）：**查特定法规名必须用 fgmc 勿用 keyword**（keyword 是全文匹配会跑偏）；content 只是命中条文段预览**不能穷尽命中条文**（枚举命中条文走②rh_ft_search）；空请求体报 500（≠②的 501"keyword 参数不可为空"）

> ⚠️ **查版本三原则（2026-08-15实测，pitfall #35）**：①查现行=通用名**不带版本后缀** ②查历史=通用名+refer_date ③**绝不要传版本后缀**（"(2012修正)"会静默误匹配旧版）；返回后核对 fwzh（主席令号）/sxx/fbrq/ssrq/fgmc
> ⚠️ **历史版本确认优先用④rh_fg_detail 整法级**（按【条旨】定位条文，无条号错位风险）；⑤rh_ft_detail 条级存在**条号错位陷阱**——不同版本条号未必一一对应（大修法规尤甚），拿现行条号套历史版可能命中"同名不同内容"的无关条文
> ⚠️ 不存在目标→code=200静默空返回——200≠查到，须检查message/data（⚠️文案区分：②rh_ft_search/③rh_fg_search="未查询到相关**数据**"；④⑤⑦⑧⑨="未查询到相关**内容**"）

### ⑥ 威科（额度层·10次·须确认）
**search_law_keyword** — 法规级关键词检索（空格分割词→返回法规列表，**不到条文级**；按发布/生效日期过滤。10次稀缺，仅在需要精确日期窗口筛法规时用，须确认）
| 参数 | 必填 | 说明 | 示例 |
|---|---|---|---|
| query | ✅ | 空格分割关键词（分词 AND） | "专利 侵权 赔偿" |
| promulgating_start_date / _end_date | 否 | 发布日期范围（YYYY.MM.DD，默认"*"不限） | "2020.01.01" |
| effective_start_date / _end_date | 否 | 生效日期范围（YYYY.MM.DD） | — |
| output_format | 否 | text/json（默认text） | "text" |

---

## 【修订历史】— 查看历次修改版本（仅法信/FLK）

### 法信（免费层·最全面）
**faxin_law_search(key_title)** → 定位法规 → **faxin_law_detail(gid)** 获取法条
**faxin_law_tab_detail(gid, tiao, tab_type="history")** — 沿革信息（历次版本对比，绿色新增/红色删除/黑色不变）

### FLK（免费层·官方）
**flk_get_detail(bbbs)** — 历史版本列表（lsyg：历次版本bbbs/title/gbrq/highLight）
→ 可选 **flk_download(bbbs)** 下载历史版本官方docx

> ⚠️ 修订历史只用法信/FLK——其他MCP无历史版本下钻能力（法信最全、FLK官方保真）
