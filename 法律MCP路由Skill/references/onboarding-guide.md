# 首次运行引导（onboarding · 详版三问）

> **作用**：总skill 第0步检测到 `data/user-profile.json` 不存在（或用户主动说"配置场景/设置偏好/重新配置"）时，按本脚本访谈一次（约5分钟），产出 user-profile.json 落盘。
> **原则**：①探测优先于自报（MCP 以当前会话实际连接为准）②一次性访谈产出文件而非记忆（换机器拷 profile 即可）③不挡路——访谈完成即进入正常流程。

---

## 访谈前准备

1. **MCP 探测**（Q2 的素材，先做后问）：
   - 列出当前宿主会话可用的工具清单（CC：已连接 MCP 的 tools；其他宿主：对应配置文件）
   - 按名称/描述关键词匹配疑似法律类工具：`law / case / 法规 / 案例 / 裁判 / faxin / flk / rmfyalk / pkulaw / yuandian / wk / qcc-legal / 法信 / 法宝 / 元典 / 威科 / 企查查法律` 等
   - 对照总skill 已知9 MCP 清单（见 `parameter-cards/README.md` 第二节），标出"已知"（框架有深度知识）与"未知"（需通用模式）；`qcc-legal-regulation` 与 `qcc-legal-case` 计入法律 MCP
   - 单独识别 `qcc-company/risk/ipr/operation/history/executive`（含下划线命名）：它们不是法律数据库，登记为企查查企业事实桥并加载 `qcc-enterprise-bridge.md`
   - **注意**：探测不到 ≠ 没有。未连接的 MCP 允许用户手动补充（记入 profile，运行时在线校验）
   - **宿主自检（2026-08-28 补，Codex 对照测试；同日 Codex hook 适配更新记账形态）**：确认当前宿主是什么——CC（有 hooks 可装自动记账）/ Codex（有 hooks 可装自动记账，装后须 `/hooks` 审核信任；未装则手动记账 + 日志可能降级落临时目录）/ WorkBuddy（手动记账）。**skill 被显式路径加载 ≠ 宿主原生发现**：Codex 只扫 `~/.codex/skills/`，未挂载时提示用户 junction/复制后再验证自动触发

2. **场景清单准备**：读 `scenario-map.md`，按 L1 六板块分组的 21 场景列表。

---

## Q1 场景（约2分钟）

出示内置 21 场景（按 L1 分组、每行带触发词摘要），问：

> "这些是内置的法律实务场景。你日常工作中主要涉及哪几类？（可多选；不确定就全选，后续可改）"
> "有没有清单之外的场景？比如你常做某个细分领域的专项工作？"

落盘规则：
- 全选 → `scenes.mode: "all"`，`enabled_L2: []`
- 勾选 → `scenes.mode: "selective"`，`enabled_L2: ["F1", "A2", ...]`
- 自定义场景 → 追加到 `scenes.custom`，**L2_id 强制 X 前缀**（X1/X2/…），至少收集 name + triggers + functions（功能组合用功能1-9编号；用户说不清就由 agent 按场景描述建议）

## Q2 MCP（约2分钟）

出示探测结果表（MCP 名 / 是否已知 / 当前是否在线），逐项确认：

> "探测到你当前连接了这些法律检索 MCP。逐个确认：①这个要启用吗？②它是什么计费模式（免费无限/定期赠送额度/免费试用/一次性付费）？③如有额度，单任务预算上限多少？"
> "还有没探测到但你想用的 MCP 吗？（允许补充，运行时会自动校验在线状态）"

落盘规则：
- 每项 → `mcp_inventory.<name>`：`{ enabled, tier( free | quota_recurring | free_trial | one_time ), budget_per_task? }`
- 未知 MCP（框架知识库外）→ 同样登记，运行时走通用模式（读 tool description 定参数、成本未知按 confirm 政策），并标 `"cost_known": false`（记账记 cost=null 不参与积分对账）
- 用户明确表示对某功能默认工具顺序有偏好 → 写入顶层 `path_order_overrides.<功能号>`（不问不写，默认空；见附录）
- 企查查法律数据 → 登记到 `mcp_inventory`，默认 `tier: quota_recurring, cost_known: true`；若用户套餐不同，以用户确认为准
- 企查查企业数据 6 组 server → 登记到 `autonomous_nonlegal_mcp` 的同一 `qcc-enterprise` 类，标 `cost_level: paid, cost_known: false`；执行时按事实桥规则一次性确认预计次数
- 其他非法律 MCP（网页等）→ 登记到 `autonomous_nonlegal_mcp`，标 `cost_level: free|paid`

## Q3 预算与确认策略（约1分钟）

> "默认确认规则如下，要调整吗？——①北大法宝+元典合计超 300 分中途预警 ②威科/元典hall_detect/超预算调用前确认 ③企查查法律数据按1/3分档位纳入任务预算 ④企查查企业数据按预计次数一次性确认，超量50%再报备、任务后核对平台账单"

落盘规则：调整则改 `confirm_thresholds` 对应项。

---

## 落盘与后续

1. 生成 `data/user-profile.json`（schema 见该文件 `_meta`），Read 回读验证 JSON 合法
2. 告知用户："配置已保存。后续说'重新配置'可重跑本引导；也可直接编辑 profile 文件"
3. 进入总skill 流程①

## 已有 profile 时（每次启动轻量校验，不访谈）

- `mcp_inventory` 中 enabled=true 的 MCP → 检查当前是否在线，不在线自动跳过（不报错、不删配置）
- `scenes.custom` 中引用的子skill → 检查 registry 是否登记，未登记则提示走通用流程
- profile schema 版本低于框架要求 → 提示重跑 onboarding 或手动升级

## 附录：speed_mode 覆盖键

- 顶层 `"speed_mode"`：`auto`（缺省，按 mcp_inventory 启用态自动三态判定，见 lightweight-protocol §二能力槽位段）/ `free`（强制免费多步路径）/ `turbo`（无条件走速度优先槽位）——**onboarding 不设访谈问题**，直接写入缺省值 auto；用户手动编辑即可切换。对无计费额度层的开源用户，auto 天然表现为 ≈free（无 enabled 额度层→自然回落免费多步路径）

## 附录：path_order_overrides 覆盖键（2026-08-28 立）

- 顶层 `"path_order_overrides"`：按功能（键 `"1"`~`"9"`）覆盖该功能的默认工具顺序，值为 MCP 名数组。**覆盖键非接管权**——空/缺失 = 照旧读速查卡与 upgrade-table 默认序（实测沉淀知识，绝大多数用户无需填）
- **onboarding 不设独立访谈问题**：仅 Q2 中用户主动表示"某功能的默认顺序不合我用"时追问并写入（如 `"path_order_overrides": { "2": ["flk", "yuandian", "pkulaw"] }`）；不问不写
- **红线不豁免**：覆盖序只调顺序——收费调用（威科/超限）仍走调用前确认，AGG 禁用、禁编造等红线照常生效
- **优先级位置**：红线 ＞ speed_mode ＞ path_order_overrides（非空才生效）＞ 子skill 覆盖约定 ＞ 卡/upgrade-table 默认序；数组中未启用/不在线的 MCP 照旧自动跳过
- 能力槽位选取（快答"档位最低一步直取"）**不受**本键影响——它只覆盖多步路径的顺序
