"""register_task.py — 注册案例库自动导入定时任务

用法：右键 → 以管理员身份运行
"""
import subprocess, sys, os

TASK_NAME = "案例库自动导入"
# 自动推导项目根（公开仓库不含本地路径）
BAT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "start_cron_import.bat",
)

result = subprocess.run(
    ["schtasks", "/create",
     "/tn", TASK_NAME,
     "/tr", BAT_PATH,
     "/sc", "weekly",
     "/d", "SUN",
     "/st", "20:00",
     "/rl", "HIGHEST",
     "/f"],
    capture_output=True, text=True, encoding="gbk"
)

if result.returncode == 0:
    print(f"[OK] 定时任务已注册: {TASK_NAME}")
    print(f"     执行: {BAT_PATH}")
    print(f"     频率: 每周日 20:00")
else:
    print(f"[FAIL] 错误码: {result.returncode}")
    if result.stderr:
        print(f"       {result.stderr.strip()}")
    sys.exit(1)
