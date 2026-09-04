# -*- coding: utf-8 -*-
# =============================================================================
# error_cases.py —— 第 1 章【实验 6：错误处理】
#
# 为什么故意出错：真实项目里"会报什么错、怎么快速定位"是基本功。
# 本脚本故意构造 4 类错误请求，记录每种错误的【异常类型 + HTTP 状态码 +
# 服务端返回信息】，形成"错误码速查表"（报告直接引用）。
#
#   A. 错误 API key（无效密钥）            -> 预期 401
#   B. 错误模型名（不存在的 model）        -> 预期 400/404
#   C. 错误 base_url（不存在的路径）       -> 预期 404/连接错误
#   D. 请求体缺字段（messages 缺失）       -> 预期 400
#
# 用法：python error_cases.py [provider]   （默认 kimi）
# 输出：终端 + evidence/ch1/06_errors.txt（证据日志）
# =============================================================================
import sys
import datetime

# openai SDK 的异常继承体系（了解它才能捕获对的异常）：
#   APIError            ：所有 API 错误的基类
#   APIStatusError      ：服务端返回了非 2xx 状态码（如 401/400/404/429）
#   APIConnectionError  ：网络层连接失败（DNS/TLS/超时）
from openai import OpenAI, APIError, APIConnectionError, APIStatusError
import common


def describe_err(e):
    """把任意异常整理成 (异常类型名, HTTP 状态码, 错误摘要)，便于统一打印。

    为什么这样分三层：
      - APIStatusError 最重要：它带 .status_code（服务端明确的错误码）
      - APIConnectionError：没拿到状态码，属于网络/连接问题
      - 其他 APIError / 未知异常：兜底，至少给出类型和消息
    """
    if isinstance(e, APIStatusError):
        # 服务端返回了状态码（401/400/404/429...），response.text 是错误 JSON
        body = e.response.text
        return type(e).__name__, e.status_code, body[:400]
    if isinstance(e, APIConnectionError):
        return type(e).__name__, "N/A(网络/连接)", str(e)[:200]
    if isinstance(e, APIError):
        return type(e).__name__, "N/A", str(e)[:200]
    return type(e).__name__, "N/A", str(e)[:200]


def run_case(provider, title, mutate=None):
    """按给定"出错变体"发起一次请求，捕获并打印错误信息。

    mutate 参数：一个函数，接收 (cfg, api_key, model)，
    返回要传给 OpenAI 客户端的请求参数（可以故意改坏任意一项）。
    这就是"故意构造错误请求"的机制——每个 case 用 lambda 改坏一处。
    """
    cfg, api_key, model = common.get_provider(provider)
    kwargs = mutate(cfg, api_key, model) if mutate else {}
    # kwargs["client"] 是传给 OpenAI 的客户端配置（key/base_url），先取出
    client = OpenAI(**kwargs.pop("client", {}))
    try:
        # 发起请求：参数里 model/messages 等都可被 mutate 改坏
        client.chat.completions.create(
            model=kwargs.pop("model", model),
            messages=kwargs.get("messages"),
            **{k: v for k, v in kwargs.items() if k != "messages"},
        )
        # 如果走到这里说明错误没触发（比如平台对坏参数很宽容）——如实记录
        common.log(f"  [意外] {title} 竟然成功了，请检查配置")
    except Exception as e:
        # 捕获并整理错误——这是本实验的重点输出
        etype, code, body = describe_err(e)
        common.log(f"  [异常类型] {etype}")
        common.log(f"  [HTTP 状态码] {code}")
        common.log(f"  [错误内容] {body}")


def main():
    """实验主流程：定义 4 个出错变体 -> 逐个触发并记录 -> 打印排查要点。"""
    common.load_env()
    provider = sys.argv[1] if len(sys.argv) > 1 else "kimi"
    cfg, api_key, model = common.get_provider(provider)
    log_path = common.set_log_file("06_errors.txt")
    common.log("=" * 72)
    common.log("实验 6：错误处理（故意触发错误并记录）")
    common.log(f"运行时间：{datetime.datetime.now().isoformat(timespec='seconds')}")
    common.log(f"证据文件：{log_path}")
    common.log(f"基准 provider：{provider}  model：{model}")
    # 脱敏展示真实 key（报告/日志安全要求）
    common.log(f"真实 key 脱敏：{common.mask_key(api_key)}")
    common.log("=" * 72)

    def base_kwargs():
        """一份【正常】的请求参数模板；各出错的 case 在它基础上改坏一处。"""
        return {
            "client": {"api_key": api_key, "base_url": cfg["base_url"]},
            "model": model,
            "messages": [
                {"role": "system", "content": "你是助手。"},
                {"role": "user", "content": "你好"},
            ],
        }

    # 4 个错误变体（每个 lambda 只改坏一个地方，便于对比"哪里错了"）
    cases = [
        # A：把 API key 换成无效值（会走不过鉴权）
        ("A. 错误 API key（无效密钥）", lambda: {
            **base_kwargs(),
            "client": {"api_key": "sk-invalid-key-0000", "base_url": cfg["base_url"]},
        }),
        # B：模型名写成不存在的（服务端找不到模型）
        ("B. 错误模型名（不存在的 model）", lambda: {
            **base_kwargs(),
            "model": "nonexistent-model-xyz",
        }),
        # C：在 base_url 后加了个错误路径（URL 不存在）
        ("C. 错误 base_url（不存在的路径）", lambda: {
            **base_kwargs(),
            "client": {"api_key": api_key, "base_url": cfg["base_url"] + "/badpath"},
        }),
        # D：messages 传 None（请求体缺必填字段）
        ("D. 请求体缺字段（messages 缺失）", lambda: {
            **base_kwargs(),
            "messages": None,
        }),
    ]

    # 逐个触发错误（注意闭包里 make=make 固定当前 lambda，避免循环变量陷阱）
    for title, make in cases:
        common.log(f"\n--- {title} ---")
        run_case(provider, title, lambda cfg_, key_, m_, make=make: make())

    # 附排查要点（把"错误码 -> 原因 -> 动作"总结成速查表，报告直接引用）
    common.log("\n[排查要点]")
    common.log(
        "1) 401 Unauthorized：key 无效/过期/无权限，检查环境变量是否设置正确；\n"
        "2) 400 Bad Request：请求体或模型名非法，检查 model 拼写、messages 格式；\n"
        "3) 404：URL 路径不存在，检查 base_url 是否以 /v1 结尾等；\n"
        "4) 429 Too Many Requests：限流，需要退避重试（报告对比分析中详述）。"
    )
    common.close_log()


if __name__ == "__main__":
    main()
