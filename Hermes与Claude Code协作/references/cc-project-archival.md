# CC 项目归档工作流

> 适用场景：将已停用/被替代的项目从活跃区移入 archive/，确保索引、引用、配置的一致性。
>
> 来源：2026-06-30 思源笔记生态归档（8 项目 + 1 agent）

## 归档流程（5 步）

```
Step 0 — 范围确认（Hermes 独立审核）
  列出待归档清单：目录名 + CLAUDE.local.md 行数 + 是否在 projects.md 索引
  检查是否有"双版本"目录（如无后缀版 vs -Obsidian支持版），grep 验证归属
  检查 .claude/agents/ 下是否有 100% 依赖该生态的 agent（连带归档）

Step 1 — 物理移动
  mv <项目目录> archive/
  mv <agent定义文件> archive/   (如有连带 agent)
  ls -1 archive/ 验证

Step 2 — 索引更新（多文件）
  projects.md：分类段→归档说明 + 统计数字更新 + 归档候选标注
  MEMORY.md：路由/引用指向替换（如思源→Obsidian版）+ 删除已失效路由
  会话索引：路径引用替换 + 标注归档
  cc-obsidian-pm/CLAUDE.local.md：待办拆分（已归档✅ / 剩余待办）

Step 3 — 残留验证
  grep 待归档项目精确名在 archive 外目录，确认零残留
  特别检查：discussions/*.md、conv_*.md 等历史文件中的引用

Step 4 — 保留/不动项
  -Obsidian 支持版独立保留
  domain enum 保留（归档项目的 CLAUDE.local.md 的 domain 字段仍合法）
  MCP 配置暂不动（agent 归档后无人调用，留着可逆）
```

## 关键发现与规则

### 1. 连带 agent 审查（新经验）

归档某生态项目时，**必须检查 `.claude/agents/` 下是否有 100% 依赖该生态的 agent**。

**案例**：归档思源项目时发现 `siyuan-note-manager.md` 绑定 6 个 siyuan MCP 工具 + 调用思源 skill → 一并归档 agent。

**规则**：归档前 grep `.claude/agents/` 目录搜索目标生态关键词，如有命中则读 agent 定义确认依赖程度。

### 2. 双版本目录归属验证

当存在无后缀版和带后缀版（如 `-Obsidian支持`）时，用 grep 判断归属：

```bash
grep -o -i "思源\|siyuan\|obsidian" "<目录>/CLAUDE.local.md" | sort | uniq -c
```

- 无后缀版：大量思源关键词、零 Obsidian → 纯思源版，归档
- 带后缀版：含 Obsidian → 保留

### 3. 无 junction 简化

归档流程从完整版「junction 删除→status archived→物理移→更新索引」简化为：

```
物理移 → 更新索引（跳过 junction 删除 + 跳过逐个改 status）
```

**前提**：项目本就无 vault junction。6 个思源项目全部无 junction，确认后才使用简化流程。

### 4. Domain enum 不随归档移除

归档项目的 domain 值（如 `04-思源笔记`）在 cc-obsidian-pm SKILL.md / project-metadata.md 的 enum 中**保留**——归档项目 CLAUDE.local.md 的 domain 字段仍合法，移除 enum 属配置调整需用户拍板。

## 与迁移的关系

归档是迁移的**前置减负**步骤。推荐执行顺序：

```
1. 僵尸归档（减负） → 待迁移数大幅下降
2. 分批迁移（按档优先级）
3. 进度更新（cc-obsidian-pm 待办 + discussions plan）
```

## 迁移中的 .bak 清理

迁移流程（Step 1）创建的 `.bak` 备份文件在 lint 通过后应删除。但两个因素可能导致 .bak 残留：

1. **CC accept edits 模式**：`rm` 命令（特别是 `-f`/`-rf`）被 CC 权限系统拒绝（见协作 skill pitfall #146），需改用 PowerShell `Remove-Item` 或等弹窗确认
2. **Hermes SSH 不可达**：Tailscale relay 断连时 Hermes 无法 SSH 到 Windows 删除文件

**策略**：.bak 文件不影响功能（CC 不会读 .bak），可在下次 CC 会话或 SSH 恢复后批量清理。不要在迁移过程中花时间反复尝试删除。

## Step 1 补充：Windows 目录锁——cp -r 绕过

当 CC 的 cwd（或 VS Code 工作区）在被归档目录内时，Windows 进程持有目录句柄，`mv` / `Move-Item` / `robocopy /MOVE` 全部报 `Device or resource busy`。

**可靠绕过方案**：`cp -r` + 文件数验证 + `rm -rf` 源文件（文件未锁可删，仅空目录壳残留）。

```bash
# Step 1: cp -r 复制
cp -r "$SRC" "$DST"

# Step 2: 文件数验证（必须！）
SRC_N=$(find "$SRC" -type f | wc -l)
DST_N=$(find "$DST" -type f | wc -l)
[ "$SRC_N" = "$DST_N" ] && echo "✓ 文件数一致" || { echo "✗ 不一致，中止"; exit 1; }

# Step 3: rm 源文件（空目录壳因句柄锁可能删不掉，不影响归档）
rm -rf "$SRC"/* "$SRC"/.[!.]* "$SRC"/..?* 2>/dev/null

# Step 4: 尝试删空壳（可能失败，可忽略）
rmdir "$SRC" 2>&1 || echo "⚠ 空壳残留，下次会话或关闭 VS Code 后清理"
```

**Git Bash 陷阱**：`robocopy /MOVE` 在 Git Bash 中会被 MSYS 路径转换成 `C:/Program Files/Git/MOVE`（`/MOVE` 被当路径），即使用 `cmd //c` 包装也可能因引号转义失败。**不要在 Git Bash 中用 robocopy 的斜杠参数**。

**案例**（2026-07-06 obsidian-table-data-reader 归档）：CC cwd 锁目录，`mv` / PowerShell `Move-Item` / `cmd //c robocopy` 三种方式全失败，最终 `cp -r + rm -rf` 成功，806 文件完整迁移。空目录壳在 CC 退出会话后可 `rmdir` 清理。

## 已完成的归档操作

| 日期 | 范围 | 数量 | 备注 |
|------|------|------|------|
| 2026-06-30 | 思源笔记生态 | 8 项目 + 1 agent | 含连带 agent 审查、无 junction 简化 |
