# 功能4 · 语义找案例（案情描述→候选案例）

> ⚠️ **调用包裹格式（本卡涉及：法信=包裹 / 元典·北大法宝·威科=平铺）**：法信侧工具参数须包一层 `{"params": {...}}`；元典/北大法宝/威科侧参数**平铺直传**，不包 params（retest-F1-20260827 建议7）。

> 升级路径（2026-08-28 扩展）：**法信拆词 → 企查查 case_search(3分，关键词拆解) → 元典case_vector_search(15分) → 北大法宝search_case(125分) → 威科search_case(10次)**
> **企查查指针**：`get_judicial_case_search` 是结构化关键词检索，不宣称原生向量语义；先把案情拆为案由+裁判争点关键词，并用地区/日期等必要过滤收窄。参数平铺，完整表见 `qcc-legal.md`。
> 类型：**分析型**——免费层多源 + 额度层至少1个 + 整体评估（升级表4.3）
> ⚠️ **RMFYALK 不建议用于拆词语义检索**——正文不支持组合检索（pitfall #8）
> ⚠️ **法信 Cookie 过期处置（2026-08-26 MCP 工具层修复后）**：检索报"Token 已过期"或返回"⚠️ Token 疑似过期"（空结果可能为过期态表现，pitfall #43）→ **直接调 `faxin_wenshu_auto_login` 工具自助刷新**（本卡法信工具均属案例侧 case server，实测 L2 登录约 39s，成功自动同步凭证），刷新后重试本检索；工具刷新失败才按降级规则"标注缺失继续"并上报总skill

---

## ① 法信 拆词（免费层·日常主力）

### faxin_case_search — 案情描述拆词检索
| 参数 | 必填 | 说明 | 示例 |
|---|---|---|---|
| keyword | 否 | **LLM把案情拆成法律概念词**（空格=AND） | "押金 返还 房屋租赁" |
| search_field | 否 | 全文内容/案例要旨/本院认为/本院查明/裁判结果/审理经过/诉称/辩称（共8种） | "全文内容" |
| casecause | 否 | 案由（逗号分隔OR） | "房屋租赁合同纠纷" |
| court / province / judgeyear | 否 | 法院/省份/年份 | — |
| tab | 否 | all/rule/case | "all" |

> ⚠️ 精细段落检索（本院认为等）**仅 tab=case 有效**，tab=rule 会返回0条
> 检索后 → faxin_case_detail(uniqid) 看完整文书

---

## ② 元典 yuandian_case_vector_search（额度层·15分·原生语义·额度层默认首选）

### yuandian_case_vector_search — 案例语义检索
| 参数 | 必填 | 说明 | 示例 |
|---|---|---|---|
| text | ✅ | 自然语言案情描述 | "房屋租赁合同到期后，房东拒绝退还押金" |
| case_type | 否 | 民事案件/刑事案件/行政案件 | "民事案件" |
| doc_type | 否 | 判决书/裁定书/调解书 | — |
| courthouse_name / courthouse_province | 否 | 法院全称/省份 | — |
| decision_date_start/end | 否 | 审结日期(YYYY-MM-DD) | — |
| size | 否 | 返回条数(1-20) | 5 |

> ⚠️ 125分/次（元典15分的8倍）——**②元典不足时才补位**（2026-08-26 调序）
> ⚠️ **实测坑位（2026-08-13）**：
> - **案号放text不精确匹配**（返回同法院同批次其他案件）——**案号精确查必须走 get_case_list 的 fulltext**（见f3/f5）
> - **案由字段与内容可能不符**（语义按内容匹配，非按案由）：如"买卖合同纠纷"案由的案子内容实为租赁——调用方勿只看 cause_of_action 字段，须读 ascertain/identified 内容确认
> - **管辖裁定类文书 `referee_result` 常空**（正常现象，非数据缺失）
> - 返回**固定13字段**（含case_grade）；4件套是**精简版3字段**（ascertain/identified/referee_result），**无原被告/争议焦点**——需深度要素研判必须用 get_case_list（29字段）
> - **所有筛选参数string单选**（case_type/doc_type/courthouse_name/province传数组全被拒）——多类型/多法院分次查询合并
> - 无Total（裸数组）；courthouse_province 须**省份全称**（"北京市"非"北京"）
> - **配合get_case_list的标准工作流**：search_case语义发现 → 拿案号 → get_case_list `fulltext="案号"` 精确核实（拿4件套）

---

## ③ 北大法宝 search_case（额度层·125分·原生语义·②补位）

### search_case — 案例语义检索
| 参数 | 必填 | 说明 | 示例 |
|---|---|---|---|
| query | ✅ | 自然语言案情（**必须语义完整**：短语"专利侵权"45条噪声11%，完整语义"侵犯专利权赔偿数额如何计算"45条0噪声——**语义完整度是决定性因素**） | "侵犯专利权赔偿数额如何计算" |
| rewrite_flag | 否 | 查询改写开关（默认true，不计费） | true |
| return_num | 否 | 返回数量（默认45纯度最高；放大如100→100条但尾部score暴跌，扩量须score过滤） | 45 |
| wenshu_filter.ay | 否 | 案由数组(OR，**完整案由名称**如"侵害发明专利权纠纷") | ["专利权权属纠纷"] |
| wenshu_filter.wszl | 否 | 文书种类数组——⚠️**只认编码"1"-"11"**（1=判决书/2=裁定书/3=调解书…），**传名称静默空返回**（pitfall #39） | ["1"] |
| wenshu_filter.fayuan | 否 | 法院名称数组(OR) | ["最高人民法院"] |
| wenshu_filter.dianxing | 否 | true=仅权威案例 | false |
| wenshu_filter.source | 否 | 权威案例来源（8类）——⚠️**仅对权威库生效，必须配 dianxing:true**，否则筛选静默无效（pitfall #40） | ["指导性案例"] |
| wenshu_filter.cj | 否 | 法院层级（精确单值：基层/中级/高级/最高） | "最高" |
| wenshu_filter.xzqh_p / xzqh_c | 否 | 省份/地级市（xzqh_p 33枚举=31省+最高+新疆生产建设兵团，无"中央"） | — |
| wenshu_filter.ja_start/end | 否 | 结案日期范围(yyyy-MM-dd) | — |

> 💡 ②③均为赠送积分——2026-08-26 调序后**默认②元典（15分）先上，③北大法宝（125分）仅补位**
> ⚠️ **实测坑位（2026-08-15，pitfall #39/#40）**：
> - **content=AI提炼的"整理后内容"（para_name分段：总结/裁判要旨/评析等），非原始文书全文**——引用原文必须下钻⑨rh_case_details（10分）
> - 短content相关性用五维信号判断：**score（严格≥0.99/宽松≥0.65）** + title + anyou案由 + wszl（裁定书天然短）+ 下钻⑨验证
> - 扩量后尾部score暴跌（45条全≥0.99 → 100条尾部0.08）——扩量须score过滤，优先改⑦⑧关键词检索
> - type字段仅普通库有（1/2），权威库无；区分库看 db 字段 + url（case/ vs qwcase/）；服务端无截断（2026-08-15实证，长响应为工具层持久化行为）

---

## ④ 威科 search_case（额度层·10次试用·仅关键难题）

### search_case — 案例语义检索（语义最强）
| 参数 | 必填 | 说明 | 示例 |
|---|---|---|---|
| question | ✅ | 自然语言案情/争议焦点 | "电商平台未对第三方卖家假冒商品尽到审查义务的侵权责任" |
| output_format | 否 | text/json | "text" |

> ⚠️ 10次稀缺——**仅关键语义难题才用**，须用户确认
