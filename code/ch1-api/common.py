# -*- coding: utf-8 -*-
# =============================================================================
# common.py —— 第 1 章实验的【公共模块】
#
# 作用：被所有实验脚本 import 的基础设施，提供三样东西：
#   1. load_env()    ：从 .env 文件读取 API key 并写入环境变量
#                      （统一变量名：ARK_API_KEY / MOONSHOT_API_KEY /
#                        DASHSCOPE_API_KEY / MIMO_API_KEY）
#   2. PROVIDERS     ：四个平台的配置表（base_url / model / 环境变量名）
#                      ——切换平台只需换 provider 名字，这就是
#                        "OpenAI-compatible 低迁移成本"的体现
#   3. log() / 日志  ：把实验输出同时打印到终端 + 写入
#                      evidence/ch1/ 下的 UTF-8 日志文件（作报告证据）
# =============================================================================
import os
import sys
import time

# ---- 强制 UTF-8 输出 ------------------------------------------------
# Windows 控制台默认是 GBK 编码，Python print 中文到重定向文件时会乱码；
# 这里把 stdout/stderr 强制设为 UTF-8，保证证据日志中文正常。
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# ---- 路径常量 --------------------------------------------------------
# BASE_DIR      ：本文件所在目录（code/ch1-api）
# EVIDENCE_DIR  ：证据日志目录（工作区根/evidence/ch1）
#                 注意：脚本目录在 code/ch1-api，往上两级才是工作区根
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EVIDENCE_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "evidence", "ch1"))

# ---- 平台配置表（任务书第 1 章统一调用脚本骨架） ---------------------
# 每个平台三个关键字段：
#   env      ：读取哪个环境变量拿 API key
#   base_url ：API 地址（OpenAI 兼容格式，以 /v1 结尾）
#   model    ：模型名（各平台命名不同）
# 用法示例：PROVIDERS["kimi"]["base_url"] 得到 Kimi 的接口地址
PROVIDERS = {
    "kimi": {
        # Kimi / 月之暗面官方文档：platform.moonshot.cn
        "env": "MOONSHOT_API_KEY",
        "base_url": "https://api.moonshot.cn/v1",
        "model": "kimi-k3",           # 旗舰推理模型（始终思考，注意 max_tokens 预留）
    },
    "qwen": {
        # 阿里云百炼（DashScope）OpenAI 兼容模式
        "env": "DASHSCOPE_API_KEY",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
    },
    "ark": {
        # 火山方舟（字节跳动），console.volcengine.com/ark
        "env": "ARK_API_KEY",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        # 火山方舟的 model 可以是：
        #   - Model ID（如 doubao-... 模型 id）
        #   - 或控制台创建的 Endpoint ID
        # 用户在 .env 里通过 ARK_MODEL_ID 指定，这里留 None 运行时读取
        "model": None,
    },
    "mimo": {
        # 小米 MiMo 开放平台：mimo.mi.com / platform.xiaomimimo.com
        # 注意点：
        #   - 默认开启思考模式，流式响应含 reasoning_content 字段（模型先想再说）
        #   - 思考模式下 temperature/top_p 参数会被服务端强制覆盖为默认值
        "env": "MIMO_API_KEY",
        "base_url": "https://api.xiaomimimo.com/v1",
        "model": "mimo-v2.5-pro",
    },
}


def load_env(path=None):
    """极简 .env 加载器。

    为什么需要它：API key 属于敏感信息，只能放在被 .gitignore 忽略的 .env 文件里；
    脚本启动时读取该文件，把 key 注入 os.environ，之后代码统一用
    os.environ["XXX_API_KEY"] 取用，全程不出现明文 key。

    实现要点：
      - 每行格式 KEY=VALUE，空行和 # 开头注释行跳过；
      - setdefault：如果环境变量已存在则【不覆盖】
        （这样在 CI/服务器场景可以直接用系统环境变量注入密钥）。
    """
    if path is None:
        path = os.path.join(BASE_DIR, ".env")   # 默认读取本目录下的 .env
    if not os.path.exists(path):
        # 文件不存在时给出提示（但不报错），让用户明确下一步做什么
        print(f"[warn] 未找到 {path}，请将 .env.example 复制为 .env 并填入 API key")
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # 跳过空行与注释行（# 开头）
            if not line or line.startswith("#") or "=" not in line:
                continue
            # partition("=") 只切第一次出现的 =，防止 key 值里含有 = 导致切错
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def get_provider(name):
    """按名字取平台配置，返回 (cfg, api_key, model)。

    这段代码是"统一调用"的核心：调用方只要传 provider 名字
    （如 "kimi"），就能拿到该平台完整的调用信息，不用关心内部细节。

    返回的三个值：
      cfg     ：PROVIDERS[name] 的副本（含 base_url 等）
      api_key ：从环境变量读出的 API key（读不到会抛异常并提供指引）
      model   ：模型名（ark 平台需要额外从 ARK_MODEL_ID 读取）
    """
    cfg = dict(PROVIDERS[name])                     # 拷贝一份，避免改到全局配置
    api_key = os.environ.get(cfg["env"], "")
    if not api_key:
        # 明确报错：告诉用户缺哪个变量、去哪里补（比让 SDK 报 401 好懂）
        raise RuntimeError(
            f"环境变量 {cfg['env']} 未设置。请先在 {os.path.join(BASE_DIR, '.env')} 中填写。"
        )
    if name == "ark":
        # 火山方舟特殊：model 可以是 Model ID 或 Endpoint ID，用户自定义
        cfg["model"] = os.environ.get("ARK_MODEL_ID", "")
        if not cfg["model"]:
            raise RuntimeError(
                "火山方舟需要 Model ID / Endpoint ID，请在 .env 中设置 ARK_MODEL_ID=你的模型ID"
            )
    return cfg, api_key, cfg["model"]


# ---------- 输出与证据记录（每个实验脚本共用） ----------

_log_file = None    # 当前实验的日志文件句柄（全局变量，脚本运行期间有效）


def set_log_file(filename):
    """开始记录证据日志：打开 evidence/ch1/<filename>，返回完整路径。

    之后调用 log() 的内容会同时写入该文件。日志用 UTF-8，
    与报告/截图构成"双证据"（截图 + 原始日志相互印证）。
    """
    global _log_file
    os.makedirs(EVIDENCE_DIR, exist_ok=True)   # 目录不存在则创建
    path = os.path.join(EVIDENCE_DIR, filename)
    _log_file = open(path, "w", encoding="utf-8")   # "w"：每次运行从新开始
    return path


def log(msg=""):
    """输出一行实验记录：打印到终端 + 追加到证据日志文件。"""
    print(msg)                                     # 终端实时可见
    if _log_file is not None:
        _log_file.write(msg + "\n")                # 文件留档
        _log_file.flush()                          # 立即落盘，防止中断丢数据


def close_log():
    """实验结束时关闭日志文件（好习惯：及时释放文件句柄）。"""
    if _log_file is not None:
        _log_file.close()


def mask_key(key):
    """API key 脱敏：只显示前 6 位和后 4 位，中间用 *** 代替。

    用途：报告/日志/截图里展示 key 状态时，不能出现完整 key。
    示例：sk-UchOU...xYtg -> sk-Uch***xYtg
    """
    if len(key) <= 10:
        return key[:3] + "***"
    return key[:6] + "***" + key[-4:]


def timer():
    """返回一个简易计时器字典（配合 elapsed 使用）。

    用法：
        t = timer()          # 开始计时
        ...做某件事...
        elapsed(t)           # 拿到耗时秒数
    """
    return {"start": time.perf_counter()}


def elapsed(t):
    """返回 timer() 开启后经过的秒数（用于统计 API 调用耗时）。"""
    return time.perf_counter() - t["start"]
