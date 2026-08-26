@echo off
REM 人民法院案例库 — 每周自动导入脚本
REM 定时任务：每周日 20:00
REM
REM 流程：检查Token → 11个sort_id检索 + 3个关键词兜底 → 去重 → 导出staging
REM 输出：由 .env 的 EXPORT_DIR 决定（默认项目内 _data\_staging\cases\）
REM 日志：<EXPORT_DIR>\_staging\cases\cron_log.txt
REM

cd /d "%~dp0scripts"
python cron_import.py
