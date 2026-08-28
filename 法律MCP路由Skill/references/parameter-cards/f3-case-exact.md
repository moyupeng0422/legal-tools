# 功能3 · 精准找案例（已知案号/案件名称）

> ⚠️ **调用包裹格式（本卡涉及：RMFYALK·法信=包裹 / 元典·北大法宝=平铺）**：RMFYALK/法信侧工具参数须包一层 `{"params": {...}}`；元典/北大法宝侧参数**平铺直传**，不包 params（retest-F1-20260827 建议7）。

> 升级路径：**RMFYALK → 法信 → 元典case_details(10分) → 北大法宝get_case_list(25分)**
> 类型：**确定型**——命中且可信即停止（升级表4.2）
> 坑位：pitfall #8（RMFYALK正文组合检索）、#16（keyword vs key_content）
> 🔁 **案号核验交叉路径（2026-08-27 立；同日复测后收窄）**：案号核验属"关键结论"的场景（如 F1.2/F1.3 覆盖约定——客户提供的案号直接决定分析方向），**免费层双源优先**：RMFYALK（case_ref）+ 法信（case_id）各查一次（RMFYALK 不可用时替代双源：法信 case_id + 元典 rh_case_details 10分，2026-08-27 复测实测）。第三源升级条件（**收窄，仅以下两种**）：
> - **源间矛盾**：两源返回**不同案件**（互相矛盾）→ 北大法宝 get_case_list fulltext（25分）裁决；
> - **双源全空** → 北大法宝 fulltext 确认案号是否真实存在。
> ⚠️ **双源一致但与客户描述不符**（如两源均命中、案由≠客户说的纠纷类型）→ **不升级**，如实报告矛盾 + 提示用户核实真实案号即可（retest-C2 教训：此情形上第三源 25 分属白花——两源一致已足证"该案号真实对应什么案件"）。
> 单源命中且无矛盾 → 即停（RMFYALK 精选库未收录≠案号不存在，勿据单源空结果下"案号错误"结论）
> ⚠️ **法信 Cookie 过期处置（2026-08-26 MCP 工具层修复后）**：检索报"Token 已过期"或返回"⚠️ Token 疑似过期"（空结果可能为过期态表现，pitfall #43）→ **直接调 `faxin_wenshu_auto_login` 工具自助刷新**（本卡法信工具均属案例侧 case server，实测 L2 登录约 39s，成功自动同步凭证），刷新后重试本检索；工具刷新失败才按降级规则"标注缺失继续"并上报总skill

---

## ① RMFYALK（免费层·官方库精确查）

### rmfyalk_search — 按案号/标题精确查
| 参数 | 必填 | 说明 | 示例 |
|---|---|---|---|
| case_ref | 否 | **案号**（推荐精确字段） | "（2019）最高法民申6342号" |
| case_number | 否 | 案例编号（库内编号） | "2021-18-2-160-001" |
| key_content | 否 | **全文关键词**（推荐，精确匹配） | "专利 侵权" |
| key_title | 否 | 标题关键词 | — |
| case_type | 否 | all/guiding/reference | "all" |

> ⚠️ **必须用 key_content 而非 keyword**——keyword 不支持空格AND，多词变单字模糊匹配（pitfall #16）
> ⚠️ **正文不支持组合检索**——多关键词拆词AND会失败（pitfall #8），只用结构化字段
> 案由用 sort_id：先 rmfyalk_get_enum(field="sort") 获取代码

### rmfyalk_get_case — 案例详情
| 参数 | 必填 | 说明 |
|---|---|---|
| case_id | ✅ | 搜索结果中的 cpws_al_id |
| sections | 否 | key_points/case_facts/judgment/reasoning/laws（不传返回全部） |

> ⚠️ 仅5500条精选且无完整判决书（pitfall #5）——需要完整文书转法信

---

## ② 法信（免费层）

### faxin_case_search — 按案号/标题精确匹配
| 参数 | 必填 | 说明 | 示例 |
|---|---|---|---|
| case_id | 否 | **案号/案例编号**（逗号分隔OR） | "（2019）最高法民申6342号" |
| title | 否 | 标题关键词 | "商标权属纠纷案" |
| keyword | 否 | 全文关键词 | "专利 侵权" |
| tab | 否 | all/rule(裁判规则)/case(普通案例) | "all" |

> 检索语法：空格=AND，`|`=OR，`not`=排除，`{N}`=间隔

### faxin_case_detail — 案例详情（完整判决书）
| 参数 | 必填 | 说明 |
|---|---|---|
| uniqid | ✅ | 搜索结果中的 uniqid |
| tab | 否 | rule/case（与搜索一致） |

---

## ③ 元典 yuandian_rh_case_details（额度层·10分·赠送积分）

### yuandian_rh_case_details — 案例详情（需案号/id）
| 参数 | 必填 | 说明 | 示例 |
|---|---|---|---|
| id | 二选一* | 案例标识（**优先级高于ah**——同传时只按id返回） | — |
| ah | 二选一* | **案号**（可返回多条：同案号权威库多来源） | "（2020）京73民初123号" |
| type | 否 | ptal(普通)/qwal(权威) 限定库 | — |

> ⚠️ **必须传案号/id**（CC审核P1-2）；若仅有案件名称无案号 → 先走 yuandian_rh_ptal_search（5分）拿 id，再查详情
> ✅ **"要完整全文必走详情"实证闭环**（2026-08-15）：同一案例检索接口content仅206字符片段，详情接口返回完整裁定书全文（含当事人/审判长/书记员落款）——检索content不完整时下钻此工具
> ⚠️ **普通 vs 权威字段体系完全不同**：普通=dsr当事人/pjjg判决结果/ssjl审理经过/yyft援引法条数组等深度字段；权威=section分节数组（关键词/裁判要点/相关法条/基本案情/裁判结果/裁判理由）+judge/lawyer恒空数组——代码处理须分支
> ⚠️ 无效案号/id→**code=200静默空返回**（message"未查询到相关内容"）——200≠查到，须检查message/data；返回最多10条

---

## ④ 北大法宝 get_case_list（额度层·25分·赠送积分）

### get_case_list — 案例关键词检索（实测2026-08-13）
| 参数 | 必填 | 说明 | 示例 |
|---|---|---|---|
| title | 否* | 标题关键词（案件名称精确查用此） | "租赁合同" |
| fulltext | 否* | 全文关键词——**⭐案号精确查用此** | "（2022）鲁0191民初3255号" |
| caseGrade | 否 | 参照级别数组(内部OR) | ["指导性案例"] |
| court | 否 | 终审法院（string单选） | "北京市高级人民法院" |
| startLastInstanceDate/endLastInstanceDate | 否 | 审结日期范围 | — |

> *title 与 fulltext 至少填一个
> ⚠️ **案号精确查询必须用 `fulltext="案号"`**（Total=1精确命中）；title放案号=0（标题不含案号）
> 返回29字段（含判决书要素4件套+依据：Ascertain查明/ControversialFocus焦点/Identified理由/RefereeResult结果/RefereeBasis依据，详见f5）
