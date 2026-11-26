> 📦 **已归档（v1.8 前历史文档）**：描述的机制已被 v1.8 架构取代，仅供历史参考。

# 协作目录迁移执行单（2026-11-22 v1.2 三方收敛版快照）

> 本文件是 2026-11-22 目录迁移的执行单快照，记录三方评审收敛过程与终版约束。
> 迁移完成后此文件归档；后续新 pair 接入参考 collab-directory-spec.md。

## 终版约束（v1.1/v1.2 修订全部采纳）

### 顺序（定稿）
T2 起新根 → T3 迁移 → T4 改路径 → T5 冻结旧根；T4/T5 间无写入窗口。
（芭迪原表述「冻结旧根→起新根」实意为新根接管后旧根冻结）

### T3 迁移规则（collab-migrate.py 实现）
- copy2 保 mtime（归位规则依赖）
- 归位：近30天→conv\ / 其余→done\YYYY-MM\ / in_*→done\ / status.json→done\YYYY-MM\status-archive-YYYYMMDD.json（历史档案，不进 quarantine）/ PROTOCOL.md 随迁冻结 / 真乱码→_quarantine 原名保留
- DEBRIS_PATTERNS（自测残骸→_quarantine）：.selftest/.acceptance/.keycheck/.ssh_probe/.tmp/dup-test/selftest/acceptance-test/probe-test/direct-test
- TOOL_FILES（→pair 根）：badi_finish.ps1/collab-migrate.py
- L100 用 os.path.relpath 拼接（replace 全局替换会误伤含同名字样的子路径）
- 幂等账本 migrate_manifest.csv + 尾部计数对账
- out/ 子结构保持；out/_archive 内容平铺进新 out\（不混 done\）
- 迁移不改名（中文 slug 原样保留）
- .badi_finish_state.json 等隐藏状态件随迁 pair 根

### 根级杂件处置（CC 补充）
旧 PROTOCOL.md 随迁冻结；MUTUAL-EXCLUSION 文档→done\2026-06\；test_*.md→_quarantine；in_kb-*→inbox\；旧 status.json 不迁为活状态（新 pair 初始化全新）

### T4 路径同步清单
- 芭迪 5 文件：status.md/stop.md/priority.md（.codebuddy\commands\hermes\）/badi_finish.ps1 $CollabDir/$KeyPath/PROTOCOL.md
- CC 4 文件：hermes-collab-feishu.md L7/L8/L108-110/projects.md L105/memory 2 处/layout-spec.md taofa.css（**迁移前对旧 out\ 路径全盘 grep**）
- Hermes：SKILL.md 注记/collab-directory-spec.md 执行记录/agent-wait.sh STATUS_REMOTE 常量

### T6 验证
芭迪执行 badi_finish 重测（新 TaskId migrate-verify|1 避幂等闸门），Hermes 验证远端落盘+INDEX 生成+旧根无新写入。

### 密钥与窗口
密钥重部署与迁移合并同一窗口（KeyPath+CollDir 一次改+一轮 T6 收口）。执行窗口=双方本地无进行中 task 空档；被进程锁定的文件会卡 Compress-Archive 与 copy2，窗口前置检查。

### conv 编号
撞车时后者改号，时间戳+发送者为准。

## 三方评审战果记录（模式可复用）
- CC 4 点：_archive 语义修正（交付物≠会话归档）/根级杂件清单（旧 status.json 不迁活状态）/顺序定稿/脚本预读+迁移后自验（计数对账+grep=0）
- 芭迪 7 点：taofa.css 断链全盘 grep/copy2 保 mtime/_quarantine 落新根（隔离区需可读可审计）/in_ 归位/status 语义统一/重测避闸门/密钥合并窗口
- 全部经 Hermes 独立分析后采纳，无传话筒
