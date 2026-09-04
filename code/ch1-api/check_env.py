# -*- coding: utf-8 -*-
# =============================================================================
# check_env.py —— 实验 1 截图辅助：环境检查 + API key 配置状态（脱敏显示）
#
# 用途：对应任务书 8/20 当天产出"环境检查截图"。
#       运行后输出：系统版本、Python/Node 版本、四个平台的 key 配置状态。
#       key 一律脱敏显示（sk-Uch***xYtg），保证截图可直接进报告。
#
# 为什么专门写判定逻辑：platform 模块在 Windows 11 上仍报告
#      "Windows 10"（微软的 NT 内核版本号约定），会误导报告读者；
#      这里改读注册表 + 用 "NT build >= 22000 即 Windows 11" 规则纠正。
#
# 用法：E:\Miniconda\envs\ML-base\python.exe check_env.py
# =============================================================================
import os
import sys
import platform
import subprocess
import datetime

import common    # 复用 .env 加载与 key 脱敏函数


def get_os_info():
    """从 Windows 注册表读取真实系统信息，返回 (系统名, build, 版本名, 注册表产品名)。

    细节：
      - winreg 是 Python 标准库，专门读 Windows 注册表（仅 Windows 可用）；
      - 关键注册表项：HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion
        * ProductName         ：微软在 Win11 上继续写 "Windows 10 Pro"（兼容约定！）
        * CurrentBuildNumber  ：如 26200（判断 Win11 的依据）
        * DisplayVersion      ：如 25H2（功能更新版本）
      - 判定规则：build >= 22000 即 Windows 11（这是社区与官方认可的规则）
      - 任何异常回退到 platform 模块的输出（保证不崩溃）
    """
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
        )
        product = winreg.QueryValueEx(key, "ProductName")[0]      # 兼容值 "Windows 10 Pro"
        build = int(winreg.QueryValueEx(key, "CurrentBuildNumber")[0])  # 如 26200
        try:
            disp = winreg.QueryValueEx(key, "DisplayVersion")[0]   # 如 "25H2"
        except OSError:
            disp = ""                                             # 老版本可能没有该字段
        winreg.CloseKey(key)
        if build >= 22000:  # Windows 11 判定规则（NT build 22000+）
            label = "Windows 11 专业版" if "Pro" in product else "Windows 11"
        else:
            label = product                                        # build < 22000 才是真 Win10
        return label, build, disp, product
    except Exception:
        # 兜底：读不到注册表就退回 platform 模块（输出可能不准，但不会崩）
        return platform.system(), 0, "", ""


# ---- 主流程（与各实验脚本不同，本脚本是"一次性输出"，逐行执行即可）----
common.load_env()                                                  # 1. 载入 .env 的 API key

os_label, build, disp, product_raw = get_os_info()                 # 2. 识别系统
print("=" * 60)
print("实验 1：环境检查与 API key 配置状态")
print(f"运行时间：{datetime.datetime.now().isoformat(timespec='seconds')}")
print("=" * 60)

# 3. 系统信息：报告纠正后的 Win11 名称 + 判定依据（为什么不是 platform 显示的 Win10）
print(f"\n[系统] {os_label}（build {build}{'，版本 ' + disp if disp else ''}）")
print(f"[判定依据] NT build {build} >= 22000 => Windows 11；"
      f"注册表 ProductName 兼容值：{product_raw}")
print(f"[platform 模块] {platform.system()} {platform.release()}（NT 内核版本号约定，"
      f"Windows 11 仍为 10.0.x）")

# 4. Python / Node 版本（任务书要求记录依赖版本）
print(f"[Python] {sys.version.split()[0]} ({sys.executable})")
try:
    # 调 node --version 拿版本号（capture_output 捕获输出，10 秒超时防卡死）
    ver = subprocess.run(["node", "--version"], capture_output=True,
                         text=True, timeout=10).stdout.strip()
    print(f"[Node.js] {ver}")
except Exception as e:
    print(f"[Node.js] 检测失败: {e}")

# 5. 四个平台的 key 配置状态（脱敏显示——截图安全的重点）
for name in ("ARK_API_KEY", "MOONSHOT_API_KEY", "DASHSCOPE_API_KEY",
             "MIMO_API_KEY"):
    val = os.environ.get(name, "")
    if val:
        # 有值：脱敏显示（只露前 6 后 4 位）
        print(f"[key] {name:<18} 已配置（脱敏：{common.mask_key(val)}）")
    else:
        print(f"[key] {name:<18} 未配置")

# 6. 安全规则提示（截图里也展示，回应任务书"截图必须遮挡 API key"）
print("\n[key 安全规则] 密钥仅存于 .env（.gitignore 忽略）；")
print("  截图/日志/报告中一律脱敏，严禁明文出现在提交物中。")
