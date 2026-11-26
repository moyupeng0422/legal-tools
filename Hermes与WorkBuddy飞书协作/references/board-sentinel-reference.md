> 📦 **已归档（v1.8 前历史文档）**：描述的机制已被 v1.8 架构取代，仅供历史参考。

# 看板机制参考（2026-11-22 v2.1 定稿）——组件/阈值/实战事故/三层防范

## 组件清单（~/.hermes/scripts/）

| 文件 | 职责 |
|---|---|
| collab_board.py v2.1 | 任务账本 CLI：append-only jsonl 事件流+派生视图。九态：dispatched/working/need_approval/waiting_review/paused/blocked/done/failed/closed |
| board_events.jsonl | 事件流（唯一事实源）：task_registered/state_changed/heartbeat/task_snapshot 每行一事件 |
| collab_board.json | 派生视图（可随时 rebuild 重建，不信任其内容；兼容旧读取方）|
| board_sentinel.sh v2 | 常驻外壳：包裹 board_watch 内核，内核退出后查看板有未收口即重启（指数退避 1s→60s、连续5次 crash 停手）；FINAL_EXIT 前 sleep 2s 二次确认；off 开关 ~/hermes/board_sentinel.off |
| board_watch.sh v2.2 | 内核：exit-on-change（30s 间隔盯全事件源）+ 收口自检（BOARD_CLEAN 连续 2 轮自退）；路径已迁新根 |
| board_cron_check.sh | **已于 2026-11-23 退役**（cronjob bc2423dbf834 删除，脚本+state 移入 scripts/_retired_20261123/）：审计裁定存档职能与 board_events.jsonl 重复且 STALL 告警无投递通道=闷死设计。board_derive 派生职责已挂载到 board_watch.sh 事件变化路径（v1.7 P0-6） |
| board_derive.py | 单写者派生器：conv_inbox 落盘 → [state:] 行 task 字段 → 自动 update 看板（芭迪零双写）|
| agent-send.sh / cc-send.sh 钩子 | SEND_OK 后自动 board add + pgrep 拉起 sentinel（谁派发谁登记）|

## 🚨 唤醒通道架构约束（三次事故复盘定案，最高优先级）

**Hermes 的唤醒本质 = 进程退出回填 stdout（terminal notify）或调度器注入（cronjob）。**

三次失败实锤：
1. nohup 拉起的哨兵：检测成功（CHANGE_DETECTED 进日志）但唤醒丢失 100%——nohup 进程不享受 notify，输出只进 /tmp 日志无注入通道
2. terminal 常驻外壳（sentinel 永不退出）：运行中输出无回填通道，事件被捕捉但永不唤醒
3. cronjob deliver=local：检测成功、输出成功，但投递地址错——local 只写文件永不进对话（曾应"不发聊天"要求改成 local 反而弄断唤醒）

**结论：进程级方案（无论怎么包装外壳）都无法同时满足"常驻+唤醒"。唯一可靠组合 = cronjob（LLM 模式 no_agent=False）+ script 空输出跳过 LLM（scheduler.py L4630 return None 实证）+ deliver=origin/local。**

**静默机制澄清（用户关切"每分钟推消息会爆炸"）**：watchdog 设计 = script 无变化 exit 0 空输出 → cronjob 静默零消息零 token；只有真实事件才发一条。deliver=origin 的事件注入不是"每分钟推消息"。

## 三层防范体系（最终形态）

| 层 | 触发条件 | 作用 |
|---|---|---|
| ① 事件变化 | 芭迪推送/CC DONE/新落盘 | 及时处理完成事件 |
| ② STALL 兜底 | 事件源无变化但任务停滞超阈值 | 每 3 分钟节流唤醒确认（时间戳 .board_stall_alert_ts 防重复刷屏）——"卡住无人察觉"的最后防线 |
| ③ 静默处理 | cronjob LLM deliver=local | 事件处理不刷用户聊天；需用户决策才 agent-send 卡片 |

**STALL 兜底实现要点**（board_cron_check.sh 无变化分支）：每 tick 跑 brief，有 STALLED DETECTED 则节流（180s）唤醒。曾失效根因：签名只含事件源不含看板状态，停滞恶化不触发唤醒——STALL 必须独立检查。

## STALL 规则 v2（只提醒绝不改状态）

| 态 | 阈值 | 语义 |
|---|---|---|
| dispatched | 5min | visible-timeout：未ACK提醒（检查唤醒链路/@丢失）|
| working | 15min | 疑似卡住 |
| need_approval | 30min | 提醒催办（用户或 Hermes 代批）|
| paused/blocked/waiting_review/done/failed/closed | 不检测 | 人工决策/等外部/已终态 |

阈值依据：CC/芭迪实测单步执行可长达 20-40 分钟（多工具链无板面事件），首档 5min 必误报（三方评审一致结论）。

**🚨 last_activity bug（v2 重写引入，已修）**：STALL 基线不能用 max(updated_at, last_heartbeat)——task_registered 的 ts 会掩盖回拨的 working 事件（registered=现在 > 事件=20min前），停滞被"刚活跃"假象掩盖。修法：独立 last_activity 字段，只有 state_changed/heartbeat 刷新，registered 不刷；STALL 基线=last_activity。

## brief 输出格式

```
⚠ STALLED DETECTED [板催办·非新任务]:
[STALL] <task_id> (<state>) 已停滞 N 分钟 → 核查卡住/唤醒失败/需催办（只提醒不改状态）
---
BOARD: N 项未收口
[need_approval] [conclusion] task_id → target stepN note   # 按 prio P0-P3 排序
```

## 唤醒处理纪律（协议 v1.2）

1. 读 board brief 全量——不是只看触发的变化
2. 处理完所有 need_approval/waiting_review/failed 项再收口 turn
3. 仍有未收口任务 → cronjob 哨兵自动值守（无需手动挂）；BOARD_CLEAN 才静默
4. STALLED 项优先核查三选一：SSH 看现场 / 检查发送链路 / 催办
5. **对用户本人汇报不挂监控直接交付完整结果**——监控盯的是外部 agent 异步回复

## 首实战事故记录（2026-11-22）

- **现象**：芭迪回复+CC DONE 都被哨兵捕捉（CHANGE_DETECTED 正常写入 /tmp/board_watch.log），但 Hermes 未被唤醒
- **根因**：agent-send nohup 拉起的进程不享受 terminal(background,notify) 的退出回填机制；nohup stdout 只进日志文件
- **修复**：cronjob 哨兵（1min 间隔可靠性 100% vs nohup 0%）；**deliver 必须选对——local 不发聊天但也不唤醒，origin 唤醒但事件会显示在对话（watchdog 静默机制保证仅事件时一条，不刷屏）**
- **教训**：检测成功 ≠ 唤醒成功；唤醒通道必须走平台原生机制；改 cronjob 投递配置前必须想清楚唤醒链路

## 事件流审计价值（实战立功）

append-only jsonl 的审计链在误报排查中立竿见影：一度误判"派生器误报"（verify-v2-r2 莫名变 waiting_review），一条 grep 事件流即还原真相——芭迪 1 分钟内完成推送、22:32 cron tick 正确派生，非 bug。**遇"状态莫名变化"先 grep board_events.jsonl 再归因。**

## 命名三处对齐（协议 v1.3，芭迪校验抓出）

**state行task= ≡ badi_finish -TaskId 传参 ≡ 看板登记名**——一个名字三处对齐。违反后果：board_derive 派生匹配失败 → 看板无法自动流转。派发通知文案中的 TaskId 必须与登记名一致（曾写错被芭迪纠正）。

## cc-send 钩子死代码陷阱

给已有脚本追加钩子前必须检查文件尾部结构：cc-send.sh 成功路径有 `exit 0`、失败路径有 `exit 1`，追加在文件尾的钩子代码**永远不可达**（死代码）。修法：钩子移入成功路径 SEND_OK 之后、exit 0 之前。追加后必须用测试消息验证钩子真实执行（看 BOARD_REGISTERED 输出）。

## 已知缺口

- ~~cc-send.sh 无自动看板登记钩子~~ 已修（v2.1 钩子移入成功路径，实测 BOARD_REGISTERED 输出正常）
- **STALL 发卡分级未实现（2026-11-23 用户裁定已入协议 §8 但代码未写）**：<10min 不告警；≥10min 向停滞方发催办卡；≥30min 升级通知用户。当天就吃教训：wm-e2e-test 收口后 watch 自动退出（设计内），芭迪 11:05/11:10 推送 R53/R54 时无哨兵→推送无人知→用户质问「10分钟自动唤醒机制也没成立」。**协议条款只写文档不写代码 = 空头支票**。实现方向=独立轻量 watcher（收口后低频值守，停滞≥10min 发卡），避免空窗重演
- **collab_board.py 无独立「核销」子命令（v1.7 发现的死锁缺陷）**：close 的 BLOCK 条件检查 pending_receipts 非空，但清理动作只在 close 成功后执行→鸡生蛋死锁，只能手动删账本行再 close。应补 `receipt <task_id>` 子命令（验证对方 [state:] 指纹后核销）
- **board_watch 多实例堆积**：每轮唤醒拉新 watch 不清旧实例（曾同时 3 个），多实例重复唤醒+浪费轮询。拉新前应 pgrep 清旧，或 agent-send WATCH_NOT_RUNNING 提醒改为检测+自动清理
- **回执账本非零时 PENDING_NOT_CLEAN 提醒无节流**：账本未清时每轮 watch（30s）都重复输出一行，日志噪音大。应加时间戳节流（同 STALL 兜底 180s 模式）
- **重跑是否递增 step 未约定**：芭迪重跑 wm-e2e-test 时自发用 step=2（指纹口径随之变化，曾致对账排查成本），协议应明确「同 task 重跑=step+1」或「重跑复用原 step」
- **指纹算法双侧一致性需审计（2026-11-23 第二次漂移）**：R54 回执指纹 bd26b08a2ccf 用已知口径（step1/2/3 × 主conv/新文件名 ASCII/UTF-8）全部无法复现，说明两侧 sha256 实现存在未对齐细节。修复前指纹只能作弱校验（对不上时以内容核对兜底，不直接判失败）
- 存储格式迁移（v1 json → v2 jsonl）时旧数据需补录快照，否则账本断代
- offline 降级（电脑睡眠误报）缓做：等真实误报 2-3 次再建心跳文件体系
- priority 排序实用化：等放开串行铁律、真有并行多任务后再启用
- **唤醒快照滞后**：board_watch 唤醒携带的 board brief 是进程周期快照可能滞后（曾报 2 项未收口实际已全收口）——唤醒后第一动作必须实时重跑 brief 甄别，不直接采信唤醒输出里的摘要

## conv 编号/命名约定

- conv 落盘文件名：conv-<slug>-YYYYMMDD-HHMM.md（wm_conv_recv 强制校验）
- 跨 agent 前缀：目前仅芭迪推送 conv_inbox（CC 走 tmux）；未来 CC 若接入统一加 cc- 前缀防撞名
- conv 段落编号撞车：后者改号，时间戳+发送者为准
