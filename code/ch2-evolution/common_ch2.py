# -*- coding: utf-8 -*-
"""
common_ch2.py —— 第 2 章实验的【公共模块】

与第 1 章的 common.py 分工不同（那套在 code/ch1-api/，偏实验 1-7 用），
这里是第 2 章四层递进实验专用的底座，提供：
  1. load_env()  ：从【第 1 章的 .env】读取 API key（两个章节共用同一个 .env）
  2. PROVIDERS   ：第 2 章用到的平台配置（kimi / mimo）
  3. set_log_file()/log()/close_log()：证据日志（UTF-8 输出到 evidence/ch2/）
  4. timer_start()/timer_end()：耗时统计

注意事项：
  - 证据目录路径：脚本在 code/ch2-evolution，工作区根要【上两级】才是
  - 日志 append 参数：断点续跑（layers.py 4 3）时用追加模式，不覆盖已跑层
"""
import os
import sys
import time

# Windows 下强制 UTF-8 输出（详见第 1 章 common.py 的说明）
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 工作区根 = 脚本目录上两级（code/ch2-evolution -> 根）；evidence/ch2 在根下
WORKSPACE_ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", ".."))
EVIDENCE_DIR = os.path.join(WORKSPACE_ROOT, "evidence", "ch2")

# 第 2 章平台配置：只用 MiMo 一个足矣（kimi 保留便于扩展对照）。
# 模型用 mimo-v2.5（非 pro 档）：输入 ¥1/M、输出 ¥2/M（访问日期 2026-08-18），
# 比 kimi-k3（输出 ¥100/M）便宜 50 倍，四层多轮实验成本最低。
PROVIDERS = {
    "mimo": {
        "env": "MIMO_API_KEY",
        "base_url": "https://api.xiaomimimo.com/v1",
        "model": "mimo-v2.5",
    },
    "kimi": {
        "env": "MOONSHOT_API_KEY",
        "base_url": "https://api.moonshot.cn/v1",
        "model": "kimi-k3",           # 对照用（预留，不默认使用）
    },
}


def load_env():
    """从第 1 章的 .env 读取 API key（两章共用同一份凭据，避免重复配置）。

    路径约定：本文件在 code/ch2-evolution，.env 在 code/ch1-api/.env，
    用相对路径 ".. / ch1-api / .env" 引用。
    实现：每行 KEY=VALUE；空行/注释跳过；setdefault 不覆盖已有环境变量。
    """
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ch1-api", ".env")
    if not os.path.exists(path):
        print(f"[warn] 未找到 {path}")
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


_log_file = None    # 当前实验的日志文件句柄


def set_log_file(filename, append=False):
    """打开证据日志文件（UTF-8）。

    append=False：覆盖写（正常运行，从头记录）
    append=True ：追加写（断点续跑时保留之前层的结果）
    返回文件的完整路径（用于日志头打印）。
    """
    global _log_file
    os.makedirs(EVIDENCE_DIR, exist_ok=True)      # 目录不存在就创建
    path = os.path.join(EVIDENCE_DIR, filename)
    _log_file = open(path, "a" if append else "w", encoding="utf-8")
    return path


def log(msg=""):
    """输出一行：终端打印 + 写入证据日志（立即 flush 防丢数据）。"""
    print(msg)
    if _log_file is not None:
        _log_file.write(msg + "\n")
        _log_file.flush()


def close_log():
    """关闭日志文件（好习惯：释放句柄，确保数据落盘）。"""
    if _log_file is not None:
        _log_file.close()


def timer_start():
    """开始计时：返回当前高精度时间戳（perf_counter 单调递增，不受系统时间影响）。"""
    return time.perf_counter()


def timer_end(t0):
    """结束计时：返回从 timer_start 到现在经过的秒数。"""
    return time.perf_counter() - t0
