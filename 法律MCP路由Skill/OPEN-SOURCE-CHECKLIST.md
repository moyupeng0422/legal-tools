# 开源打包清单（OPEN-SOURCE-CHECKLIST）

> **作用**：法律MCP路由Skill 开源发布时的边界定义与剔除清单。框架化改造（2026-08-21）已把机制层面的硬编码降到最低，剩余项按本清单处理。
> **状态**：边界已定义（2026-08-21 本轮），实际打包发布留待后续单独一轮。

---

## 一、开源包内容（include）

```
SKILL.md                                # 总skill（框架化后无用户特定内容）
references/                             # 全部：知识库层（速查卡/坑位/升级表/字典/改造指南/onboarding）
subskills/                              # F1 + _TEMPLATE-wrapper.md（发布策略三决策 2026-08-26：D2壳/A2融合
                                        # 剔除不随包——D2 指向作者本地原skill跑不通，用户按模板自建子skill）
scripts/                                # 辅助脚本（log_usage / verify_usage / preflight / hall_detect）
  + scripts/.env.example                # 模板化（见剔除清单第5条）
  + scripts/preflight.py                # 凭证预检（2026-08-28 入包）：第0步开工前探 测法信/rmfyalk 凭证
                                        # 推算状态，只探不刷；相对路径定位（SKILL_DIR.parent 兄弟目录
                                        # 约定），目标库缺失自动降级 ⚪ 不报错
  + scripts/hooks/                      # CC/Codex 宿主可选增强（2026-08-28 入包，同日 Codex 适配）：
                                        # auto_log_hook.py + backfill_from_transcript.py +
                                        # hooks-settings.example.json + hooks-codex-example.json +
                                        # README.md（多宿主声明；<SKILL_DIR> 占位符已模板化）
  + scripts/transcript_parsers.py       # 会话留痕解析共享模块（2026-08-28 Codex 适配入包）：
                                        # CC transcript / Codex rollout 自动探测，补记+对账共用
data/
  ├── subskills-registry.json           # 发布版只留 F1 登记 + fallback 说明，剔除 D2/A2 条目与
                                        # redirects.B1（三决策#3）；_meta note 加"示例指向作者本地skill，请替换"
  └── discipline-check.md               # 保留——模板
OPEN-SOURCE-CHECKLIST.md                # 本文件（或发布时删除）
README.md                               # 已定稿（2026-08-28 主本=最终发布口径：示例章节只留F1，
                                        # 已补快答/轻量协议/preflight/hooks 章节）
```

## 二、剔除清单（exclude）

| # | 文件 | 原因 | 处理 |
|---|---|---|---|
| 1 | `CLAUDE.local.md` | 含 D:\workbuddy 路径、CC×WorkBuddy 协作模式、内部进度/防错记录 | 不拷入 |
| 2 | `discussions/`（内部审核讨论，全部） | 内部过程记录 | 不拷入 |
| 3 | `data/mcp_usage_log.jsonl` | 真实调用成本记录（含任务名等用户数据） | 换为空模板（保留 init 示例行） |
| 4 | `data/_check.txt` | 内部检查残留 | 已删除（2026-08-21，git rm） |
| 5 | `scripts/.env` | 密钥配置结构 | 改为 `.env.example`（只含变量名+空值） |
| 6 | `data/user-profile.json` | 个人偏好配置（场景勾选/MCP预算/确认阈值）。**若随包发布，SKILL.md 第0步会检测到文件存在而跳过 onboarding，新用户将误用作者配置** | 不拷入（推荐）——新用户首次运行自动触发 onboarding 生成；README 说明"首次运行自动引导配置"。如需提供示例参考，改名 `user-profile.example.json`（框架只认 `user-profile.json`） |

## 三、发布前 grep 扫描清单（已知残留点）

以下硬编码在**功能上必要**（本机运行时真实路径），发布时按对应方式处理：

| 位置 | 内容 | 发布处理 |
|---|---|---|
| `scripts/verify_usage.py` | `DEFAULT_TRACES = "<本地用户目录>/.workbuddy/traces"`（已随 v1.0.0 发布处理：改为环境变量 `TRACES_DIR` / 运行时 `--traces-dir`，未提供则跳过 traces 对账） | ✅ 已处理 |
| `references/pitfall-checklist.md` #29/#32 | 本机脚本绝对路径（如 `<自研仓库>/法信MCP/auto_login.py`） | ✅ 已处理——改写为"运行你本地的法信 auto_login 脚本（自建 MCP 用户的本地路径）"，保留坑位机制、去掉绝对路径 |
| `subskills/legal-scene-D2-ad` | 壳模式固有：指向作者本地原skill | ✅ 已处理——发布包不含 D2 壳（用户按 `_TEMPLATE-wrapper.md` 自建子skill） |
| `data/subskills-registry.json` source_skill / redirects | 本地 skill 名称（广告合规审核/案例智能对比/企业尽调备忘录） | 作为范例保留可（产品/项目名非隐私），但发布版 note 中加一句"示例指向作者本地 skill，请替换为你自己的" |
| `references/subskill-adaptation-guide.md` 示例 | 同上（示例 JSON 中的 source_skill） | 同上，示例性质可保留 |

## 四、发布前检查命令

```bash
# 本地路径残留（应只剩第三节清单内的已知项）
grep -rn "D:\\\\\|D:/claude\|C:\\\\Users\|C:/Users" SKILL.md references/ subskills/ scripts/ data/ --include="*.md" --include="*.py" --include="*.json"
# API key 格式
grep -rn "sk-\|Bearer [A-Za-z0-9]\{20,\}\|API_KEY=" scripts/ --include="*.py"
# 协作字样
grep -rn "WorkBuddy\|HUAWEI" SKILL.md references/ subskills/ scripts/ data/
```

## 五、发布前 README 核对项（2026-08-28 起草完成，打包时逐项核对）

- [x] 框架定位（五层架构图+宿主增强层）+ 首次运行 onboarding 流程说明（无 profile 自动触发，约5分钟三问访谈）
- [x] **FAQ：`speed_mode` 覆盖键解释**——"我的 profile 里 speed_mode 是 auto，要不要改？"：未安装计费 MCP 时 auto 天然表现为免费多步路径（能力槽位无 enabled 额度层可满足→自然回落），无需手动改 free；详见 references/onboarding-guide.md 附录
- [x] 已知 7 MCP 的支持情况（哪些需要自建 server、哪些直连）
- [x] 子skill 改造指南入口（references/subskill-adaptation-guide.md）+ 壳模板使用法
- [x] 免责声明（法律检索辅助工具，非法律意见）
- [x] 快答模式/轻量分发协议/preflight/hooks 机制章节（2026-08-28 补）
- [ ] 打包时终检：示例章节确为"只留 F1"口径（本节上一条勾选项打包时再核一遍）
