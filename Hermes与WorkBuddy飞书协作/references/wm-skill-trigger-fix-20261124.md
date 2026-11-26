# wm skill 漏触发调查与修复（2026-11-24，task=wm-skill-trigger-check）

> 状态：诊断闭环，修复方案 R3 已收敛**待用户拍板**（a/b 选一 + UI 版本核实）。后续执行时更新本文件。

## 背景

用户在 WorkBuddy 其它对话让芭迪处理「拜访客户」类工作，work-management skill 未触发（skill 2026-11-23 建成、已注册）。

## 诊断结论（芭迪 R1→R3，Hermes 逐轮核验）

1. **4 月温州医科大学那次不算漏触发**：wm-local/skill 当时不存在（7 个月时间差）。但芭迪 R1 曾据此误判「无反例、非触发失灵」——被新反例推翻。
2. **浙能集团拜访备忘（11-24）= 建成后漏触发实锤**：`projects\d-workbuddy\a68c7744-....jsonl`（680 行）——0 次 work-management skill、0 次 wm-local 实调、12 处「本地」全指外部；被 company-investigation-memo（尽调 skill）吸附，走 WebSearch×46+企查查，产出尽调备忘而非查本地档案。
3. **根因（芭迪 R3 实证）**：customPrompt 注入内容 `has_wm_route=False`、`has_skill_scan=False`——无「先扫 skill」通用纪律、无 wm 路由，触发全靠 LLM 语义自觉，「拜访备忘」请求措辞被归为尽调类。
4. **枚举盲区教训**：vscdb 旧索引（19 会话全在 3~4 月）与 projects/*.jsonl 新正文并存，只查前者会漏新会话。

## 用户拍板的方向（R3，2026-11-24）

- ❌ P1「堆触发词」作废。✅ 改 **CC 式通用纪律**：「任何工作任务先扫 skills 列表，沾边（哪怕部分相关）就加载，宁可多载不可漏载」。
- 落点=customPrompt 常驻层（skill 内写会循环依赖，框架层无注入点），合并一段写：通用纪律在前+客户/案件 wm-local 特例在后。
- 落盘=用户在 UI 设置手动改（芭迪无 UI 写权限）。

## 待拍板：字符取舍（customPrompt 实存 1424/1500，余量仅 76）

- **方案 a**：只加 ~72 字精简纪律（卡进余量，不动其它）——但无 wm 特例，尽调吸附风险残留。
- **方案 b**：加 ~150 字合并版（通用纪律+wm 特例），同时把「协作 N」6 行示例压成 2 行腾 ~80 字符——治本，但动既有内容。
- ⚠️ 前置疑点：UI 实存 1424 ≠ 11-23 定稿 1375，内容版本存疑，用户需先核实 UI 当前内容。

## 关键锚点

- 载体：`C:\Users\<windows-username>\.workbuddy\app\app-config.json` → `personalization.customPrompt`（SHA256 前 12 = a05ec33ebde3，raw_len=1424），注入 `<user_custom_instructions>`，改后新会话生效
- conv 存档：conv_inbox/conv-wm-skill-trigger-check-20261124-{1758,1816,1826}.md（R1/R2/R3）
- 推荐措辞（合并版）：R3 conv（conv-wm-skill-trigger-check-20261124-1826.md）§step-4 ②(2)(4) 有全文
