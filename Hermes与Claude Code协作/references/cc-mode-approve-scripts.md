# CC 协作模式切换与权限批准脚本（2026-11-22 定稿 v2，Hermes×CC R1→R2 辩论+三轮实测验收）

> **架构终审补记（2026-11-22 晚）**：曾讨论用 CC 侧 hooks（SessionStart 会话自注册 / Stop TASK_MAP 落库 / hook 检测方案类输出提醒辩论）替代部分脚本。**最终全否决**：①SessionStart=伪需求（session_id 在协作协议中无消费场景，会话绑定靠任务名+task_map）②Stop 帧文本提取够用③正则判"方案类"必然漂移，改为协议自声明字段 `output_type: analysis|execution`（CC 是输出作者，自知事实）。**hooks 零落地的三个教训**：项目级隔离覆盖不了"协作不限于工作管理"的场景；PowerShell GBK 编码坑；本地 hook 不能发 tmux 键。复评触发条件：CC 官方支持更细粒度 hook 作用域且跨项目场景出现真实痛点。

## 模式↔任务阶段映射（硬前置，发消息前必查）

| 任务阶段 | 模式 | 命令 |
|---------|------|------|
| 发 TASK/讨论实施方案/辩论 | plan（⏸ plan mode on） | `~/.hermes/scripts/cc-mode.sh plan` |
| CC 执行操作（写文件/跑命令） | auto（⏵⏵ accept edits on） | `~/.hermes/scripts/cc-mode.sh auto` |
| 查当前模式 | — | `cc-mode.sh status`（幂等，已是目标模式直接 OK） |

**残留风险备注（无技术兜底，靠流程纪律）**：plan 模式下发执行类 TASK 会触发 ExitPlanMode 弹窗——发 TASK 前必查模式。

## cc-mode.sh（模式切换）

- 机制：前置空闲检查（无弹窗/无 esc-to-interrupt）→ 循环 BTab+读状态栏到位即停 → 帧稳定验证
- MODE_BUSY=会话非空闲拒绝切换；MODE_STUCK=连续 2 次 BTab 无变化（有东西挡着，停止上报）
- ⚠ 弹窗悬着时 BTab 语义=挪弹窗光标，绝不盲按

## cc-approve.sh（权限弹窗处理，用户裁定模型：Hermes 决策选号+脚本承载机械操作）

```
cc-approve.sh dump      # 只读弹窗全文+CLASSIFICATION 分类，不按键
cc-approve.sh <N>       # 批准选项 N（脚本处理按键/验证/帧稳定/排队弹窗全链路）
cc-approve.sh cancel    # 关闭弹窗（无弹窗时拒绝——Esc 会中断运行中 turn）
cc-approve.sh --allow-persist <N>  # 显式批准"不再询问"类持久化选项
```

- 分类三档：AUTO_OK（常规命令）/ NEED_REVIEW（含凭证字样，需 ALLOW_REVIEW=1 确认）/ HUMAN_REQUIRED（黑名单：Bypass Permissions/配置文件写入/hooks·MCP 信任/删除/信任提示/安全分类器拦截）
- 黑名单唯一放行通道：**用户亲手** `touch ~/.hermes/HUMAN_OK`（一次性，用后即焚，审计日志）
- persist 选项 fail-closed 防护；gate-zero 选项存在性校验（状态失步绝不按键）
- Enter 直通路径：ExitPlanMode 类弹窗不响应数字键（> 已在选项上时直接 Enter）
- 与 cc-wait.sh 分工：wait 只报「有弹窗」，approve 接手处理

## 实测记录（2026-11-22 三轮验收）

- CC pane 视角审查抓出 P1×3（旁路违背定稿/persist fail-open/无 gate-zero）+ P2×3，全部修复后实测
- 实测通过：三态切换含幂等、AUTO_OK 分类、Enter 直通 APPROVE_OK、CANCEL_NO_DIALOG 防护
- 经验：ExitPlanMode 弹窗构造成功路径=cc-mode.sh plan→发「请调用 ExitPlanMode」；常规 Bash 命令在本 pane 沙箱下静默放行不弹窗
- 教训：分类函数必须只读弹窗区块（sed -n "/^╌+/,$p"）——读全文会把 CC 正文引用的黑名单词误判为 HUMAN_REQUIRED
