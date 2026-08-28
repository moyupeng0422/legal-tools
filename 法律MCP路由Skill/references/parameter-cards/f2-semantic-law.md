# 功能2 · 语义找法条（只有问题描述）

> ⚠️ **调用包裹格式（本卡涉及：FLK·法信=包裹 / 企查查·元典·北大法宝·威科=平铺）**：FLK/法信侧工具参数须包一层 `{"params": {...}}`；企查查/元典/北大法宝/威科侧参数**平铺直传**，不包 params。企查查完整参数见 `qcc-legal.md`。

> 升级路径（2026-08-28 扩展）：**FLK拆词 → 法信拆词 → 企查查 article_semantic_search(3分) → 元典law_vector_search(15分) → 北大法宝search_article(125分) → 威科search_law(10次)**
> **企查查指针**：`get_legal_article_semantic_search(query[, regulationName/effectStatus/effectRank/effectScope/日期过滤])`，自然语言问题最长500字符，3分；关键词已经明确时改用 `get_legal_article_search`（1分）。完整表见 `qcc-legal.md`。
> 类型：**分析型**——免费层多源互补 + 额度层至少1个 + 整体评估（升级表4.3）
> ⚠️ **效果敏感场景**：找错法条比花钱更糟
> ⚠️ **法研排除**：不用于语义找法条（无语义引擎、拆词检索差）——坑位清单 pitfall #19
> ⚠️ **法信 Cookie 过期处置（2026-08-26 MCP 工具层修复后）**：检索报"Cookie 已过期"或返回"⚠️ Cookie 疑似过期"（空结果可能为过期态表现，pitfall #43）→ **直接调 `faxin_laws_auto_login` 工具自助刷新**（本卡法信工具均属法规侧 laws server，实测 L2 登录约 39s，成功自动同步凭证），刷新后重试本检索；工具刷新失败才按降级规则"标注缺失继续"并上报总skill

---

## ① FLK 拆词（免费层·日常主力）

### flk_high_search — 高级检索替代语义（LLM把问题拆成条件）
| 参数 | 必填 | 说明 |
|---|---|---|
| conditions | ✅ | 条件数组，每条 {field_name, values[], search_type, link} |
| page_num / page_size | 否 | 分页（max 50） |

**conditions 结构**：
| 子参数 | 说明 | 示例 |
|---|---|---|
| field_name | title / content / gbrq / sxrq / flfg_code_id / zdjg_code_id / sxx | "content" |
| values | 文本：关键词；日期：["起","止"]；分类：codeId | ["试用期解除"] |
| search_type | 1=精确 2=模糊 | 2 |
| link | 与前条件关系：0=AND 1=OR 2=NOT | 0 |

**拆词示例**：
```
问题："员工试用期被辞退能拿赔偿金吗？"
拆词：content="试用期解除" link=0（AND）
      content="经济补偿" link=0（AND）
```

> ⚠️ values 数组**不应放多个词**（行为不可控），多词拆成独立 condition

---

## ② 法信 拆词（免费层·补充）

### faxin_law_search — 全文关键词检索
| 参数 | 必填 | 说明 | 示例 |
|---|---|---|---|
| key_content | 否* | 全文关键词（LLM拆解后的法律概念词） | "试用期解除" |
| database | 否 | 子库（默认gjfl；港澳/条约须指定子库） | "gjfl" |
| search_mode | 否 | 推荐"全文模糊" | "全文模糊" |

> *key_title/key_content 至少一个；检索后 → faxin_law_search_articles(gid, 关键词) 定位条文

---

## ③ 元典 yuandian_law_vector_search（额度层·15分·原生语义·额度层默认首选）

### yuandian_law_vector_search — 法条语义检索
| 参数 | 必填 | 说明 | 示例 |
|---|---|---|---|
| text | ✅ | 自然语言问题/案情描述 | "用人单位违法解除劳动合同，劳动者可以主张哪些赔偿或补偿？" |
| timeliness | 否 | **建议必加"现行有效"**（防返回失效法条；⚠️string单选） | "现行有效" |
| lib | 否 | 中央/地方 | — |
| issue_department | 否 | 制定机关全称 | "全国人大常委会" |
| implement_date_start/end | 否 | 施行日期范围(YYYY-MM-DD) | — |
| size | 否 | 返回条数(1-20) | 3 |

> ⚠️ 125分/次较贵（元典15分的8倍）——**③元典边界命中/失败时才补位**
> ⚠️ 实测法规语义需优化（未命中劳动法39条）——性价比存疑（2026-08-26 调序依据，见升级表功能2💡）
> ⚠️ **实测坑位（2026-08-13）**：timeliness **string单选**（传数组被拒，与get_law_list不同）；**无Total字段**（不知全量命中）；article字段常空（办法/复函/通知类命中"法规级"多于"法条级"）；**无翻页**（page被拒）；错别字容错（"劳动合约"→命中劳动合同）

---

## ④ 北大法宝 search_article（额度层·125分·原生语义·③补位）

### search_article — 法规语义检索
| 参数 | 必填 | 说明 | 示例 |
|---|---|---|---|
| query | ✅ | 自然语言查询（**错别字/口语化容错**："劳动合约"仍命中劳动合同法87条） | "试用期解除劳动合同的赔偿标准" |
| rewrite_flag | 否 | 查询改写开关（默认true，**不计费**）。**精确查证用 false**（已知要点、防改写引入偏离概念）；口语化/模糊案情用 true | true |
| return_num | 否 | 返回法条数量（默认45，可放大但尾部噪声随条数增大） | 45 |
| fatiao_filter.sxx | 否 | 时效性——⚠️**语义只认"现行有效"**，传"失效"/"已被修改"返回空（查失效走②rh_ft_search 或 ④⑤refer_date） | ["现行有效"] |
| fatiao_filter.effect1 | 否 | 效力级别（**17级**枚举，但⚠️**语义库仅覆盖10级中央法条**——宪法/法律/司法解释/行政法规/监察法规/部门规章/党内法规/军事法规规章/行业团体规范/地方规范性文件） | ["法律"] |
| fatiao_filter.law_start/end | 否 | 实施日期范围(yyyy-MM-dd) | — |

> 💡 ③④均为赠送积分（定期补）——2026-08-26 调序后**默认③元典（15分）先上，④北大法宝（125分）仅补位**
> ⚠️ **实测坑位（2026-08-15，pitfall #37/#38）**：
> - **7种地方类/工作文件类层级语义检索必空**（地方性法规/地方政府规章/地方律协规定/地方司法文件/自治条例/立法机关工作文件/行政机关工作文件——数据存在但向量索引未收录，4重验证确认）——**查这类层级直接改 rh_ft_search(5分)**，勿在语义检索反复重试
> - **结果混入 type=2 案例 / type=3 通知**——**必须 `filter(item.type==1)`** 才是真法条
> - **fatiao_filter 服务端只认 4 字段**（sxx/effect1/law_start/law_end），传 type 等额外字段静默忽略
> - 无 Total、无翻页（page 静默忽略），return_num 即全部可得

---

## ④-2 元典关键词兜底（语义必空/需精确过滤时·5分）

### yuandian_rh_ft_search — 法条关键词检索（★默认首选，全17级+失效法条）
| 参数 | 必填 | 说明 | 示例 |
|---|---|---|---|
| keyword | ✅ | 关键词（空参→501报错） | "试用期 解除" |
| search_mode | 否 | AND（默认）/OR——keyword 空格拆分拼接 | "AND" |
| fgmc | 否 | 法规名过滤（⚠️**空格=AND 全命中**，与 sxx/dy/fbbm 的空格=OR 规则不同） | "劳动合同法" |
| xljb_1 / sxx / dy / fbbm | 否 | 效力17级（空格OR）/ 时效（**全时效可用**，"失效"可查）/ 地域（**含"中央"**，与案例侧 xzqh_p 枚举不同）/ 发布部门 | — |
| fbrq/ssrq_start/end | 否 | 发布/实施日期范围(yyyy-MM-dd) | — |
| top_k | 否 | 默认10；⚠️**51→51条软上限**（文档"max50"不符），**建议≤20** 防响应体爆炸 | 10 |

> ✅ **content 即完整条文原文**（2026-08-17 指南实测，与⑤rh_ft_detail 逐字一致）——检索定位后**引用无需下钻⑤**
> ⚠️ 校验：`ft_num` 须含"第X条"（区分真法条 vs 章节序号/批复类非典型条文）；无 Total、无翻页
> 💡 另有 ③rh_fg_search（法规目录查询器，f7卡）：keyword 可省、纯过滤枚举法规清单（独有）；⚠️查法规名用 fgmc 勿用 keyword、content 不能穷尽命中条文（pitfall #44）

---

## ⑤ 威科 search_law（额度层·10次试用·仅关键难题）

### search_law — 法规语义检索（语义最强）
| 参数 | 必填 | 说明 | 示例 |
|---|---|---|---|
| question | ✅ | 自然语言问题 | "劳动者在试用期被辞退，用人单位是否需要支付经济补偿金？" |
| output_format | 否 | text/json | "text" |

> ⚠️ **唯一命中劳动法39条的MCP**——语义最强但10次稀缺，**仅关键语义难题才用**，须用户确认
