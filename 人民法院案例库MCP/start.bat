@echo off
REM 人民法院案例库 MCP Server 启动脚本
REM
REM 按需登录模式：Token 过期时通过 rmfyalk_auto_login 工具自动刷新
REM .env 中配置 RMFYALK_TOKEN 作为初始 Token
REM
cd /d "%~dp0scripts"
python server.py
pause
