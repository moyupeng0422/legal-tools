# CC×芭迪 B 方案（芭迪驱动 CC）知识库

> 2026-11-25 全链路落地并**当日收官（step1-10 全闭环）**。skill 本体装芭迪侧 `C:\Users\<windows-username>\.workbuddy\skills\badi-drive-cc\`（SKILL.md v1.1.1 + scripts\badi-cc-*.ps1 七件套），权威手册在那份 SKILL.md，本文只记 Hermes 侧需要知道的协作事实与踩坑。sha12 基线（byte 口径）：common e3517b3e3750 / wait ef4eb268b07f / SKILL c7f01c4c2484。

## 架构一句话

WorkBuddy 框架回收子进程 → 不做进程常驻，做**固定 session-id 会话常驻**（首轮 `--session-id`、后续 `--resume`，一次性 `-p` 进程+stream-json 事件流）；send 同步阻塞 → 芭迪**单回合闭环**（多轮 send/wait/verify 含辩论 R1→R2→R3 全部达标才结束回合汇报）。完成判定三条件：result 事件 + 落盘 verify PASS + 重要任务内容实质审读。Hermes×CC 移植采纳：辩论/指令自包含/done 只升不降/不编造成功红线/实质审读；不引入：ACK 指纹/弹窗监控/短消息分段/心跳。

## 目录双分离（用户拍板）

- skill 本体（只读）：`C:\Users\<windows-username>\.workbuddy\skills\badi-drive-cc\`
- CC×芭迪运行时根（独立于 hermes-badi）：`D:\<workbuddy-root>\collab\cc-badi\{cc-sessions\_turns, tasks\}`
- 草稿暂存：`D:\<workbuddy-root>\collab\hermes-badi\reports\cc-suite-draft\`（改脚本要同步两处副本，sha12 字节级比对）

## Git Bash fstab 修复全记录（2026-11-25，✅已根治）

**坑**：本机 Git Bash mount 表缺 `/d` `/c` 短挂，裸 `/d/` 解析为 `C:\Program Files\Git\d\` 字面目录（CC 写文件落错位置、CC 与驱动方各看各的视图，CC 没说谎）。正确路径=`/cygdrive/d/` 或 `D:/`。

**修复过程与实证**：
1. 芭迪无法修：账号非管理员，`Git\etc` 目录 ACL 仅 Administrators 可写，UAC 提权被安全钩子封死——**Program Files 写入只能用户亲手**
2. 用户管理员写入两字段版（`D:/  /d/`）和六字段版（`D: /d ntfs binary,posix=0,auto 0 0`）均不生效，mount 表不变，且无解析报错（格式错误应有 `invalid fstab option` 警告）
3. **最终根因（13:31 实证）**：msys/Cygwin mount 表存共享内存，机器上有活的 msys 进程（昨天启动的 bash/sh，即 CC bridge tmux 会话）→ 新进程挂旧共享表，**fstab 不被重读**。两个正确格式版本可能都对，只是被缓存挡住
4. **生效条件：全部 msys 进程退出后首个新进程重建 mount 表**（重启电脑最稳；或杀光 bash/sh 后新起进程验证）——实测杀 3 个残留 bash/sh 后 cygpath 立即输出 `D:\`，六字段条目本来就是对的
5. 验收探针：`& "C:\Program Files\Git\usr\bin\cygpath.exe" -w /d/` 输出 `D:\` 即成功（PowerShell 裸引号路径后跟参数不执行，**必须加 & 调用运算符**——Hermes 给用户的验收令未适配 PS 语法致其报错，给用户手动命令时先想目标 shell）
6. **进程身份误判教训（step8）**：杀 msys bash/sh 前我预判「那是 CC tmux 会话、CC 会断」——实为本机无 tmux（凭旧印象推断未实证），CC bridge 的 claude.exe 与 lark bridge 独立存活未受影响。杀进程前先查目标进程树父子关系，勿凭端口/名字想当然

**附赠修复（step7）**：`Test-CygpathHealth.healthy` 原只判 `/cygdrive/d/`（恒 True，告警形同虚设），已改判 `$slash_d -like 'D:*'` + MIS-MAPPED 警告带实际值；`cygdrive_ok` 字段解耦保留。

## 迭代修订史（step5-10，全部经 Hermes 独立验收）

- **step5 三项修订**（用户拍板）：目录双分离（skill 只读/运行时归口）；单回合闭环原则入 SKILL 顶部；Hermes×CC 机制移植清单（5 采纳 4 不引入）
- **step6 安装**：8 文件落 skill 位+运行时根骨架；fstab 受阻（ACL 非管理员）如实上报；发现 healthy 判据缺陷
- **step7**：healthy 改判 `$slash_d -like 'D:*'`，MIS-MAPPED 警告带实际值生效（fstab 未修时正好当告警分支测试环境）
- **step8**：fstab 生效后 healthy=True 翻转验证；CC 会话误判纠正（见上）
- **step9 首跑实测**：13min 单回合闭环、1.99 USD/轮、Write×3/Bash 只运行、三条件判定全过。新坑 N1-N5：N1=WorkBuddy 安全策略拦 CC 派生链 reg.exe 但任务实际成功→**判完成只认磁盘/事件流不认工具返回文本**（最重要）；N2=path guard 误报 `/cygdrive/d/`；N3=stop 的 cost_total 恒 0；N4=PS5.1 读中文须 `-Encoding UTF8`；N5=复杂任务 budget 上调
- **step10 收尾**：N2=先剥 `/cygdrive/<盘符>/` 整段再匹配裸短路径；N3=wait 成功后 cost 累加回写 state（同 turn 幂等）；N1/N4 固化为 SKILL P8/P9；budget 区间 0.7–2.0 USD 复杂任务 3–5。备份 `*.bak-20261125-step7/step10` 保留待统一清理

## 协作纪律（实战验证）

- **涉及芭迪的内容让芭迪自己改，Hermes 只审查**（用户拍板）：派修订任务卡=要求+验收标准，她执笔出 conv（SKILL.md 全文+diff+逐条「已落实/有异议」），Hermes SSH 拉回独立算 sha12/内容抽查，不信自报
- **验收口径先约定**：sha12 有字节级（含 BOM）与无 BOM 正文两种口径，混用会误判不一致
- 她的边界感好：超授权范围不动（如 fstab）、发现 upstream bug 主动上报不擅自改、失败如实报不编造（三次 ACL 失败全数上报）
- WorkBuddy 新装 skill 需重启会话才进注册表（同 wm-local MCP 现象），但她本会话实测框架加载器可直接加载
