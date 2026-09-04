# -*- coding: utf-8 -*-
# =============================================================================
# unified_call.py —— 第 1 章【实验 3：Python 统一调用脚本】
#
# 任务书要求：写一个脚本，通过 provider 名称切换 base_url / model / api_key，
#             同一问题同时调用两个模型，输出响应内容与 usage（token 用量）。
#
# 核心思想（"OpenAI-compatible 低迁移成本"的演示）：
#   四个平台都兼容 OpenAI 接口——同一段 SDK 代码，只改 3 个东西就能换平台：
#     base_url（接口地址）、api_key（密钥）、model（模型名）
#   这些配置都集中在 common.PROVIDERS 里，脚本本身完全不用改。
#
# 用法：
#   python unified_call.py             # 默认调用 kimi + qwen
#   python unified_call.py kimi mimo   # 指定任意两个 provider
# 输出：终端 + evidence/ch1/03_unified_call.txt（UTF-8 证据日志）
# =============================================================================
import sys
import datetime

from openai import OpenAI    # 官方 OpenAI SDK，也是国内平台通用的客户端
import common                 # 公共模块：.env 加载、PROVIDERS 配置、日志


def call_one(provider: str, prompt: str):
    """对单个平台发起一次普通（非流式）调用。

    参数：
      provider：平台名（"kimi"/"qwen"/"ark"/"mimo"）
      prompt  ：要问的问题（用户消息）
    返回：
      (回答内容, usage 对象, 耗时秒数)
    说明：
      - 所谓"统一调用"= 换平台时只有第 1 行取配置的方式变了
      - messages 里的 system（系统指令）+ user（用户问题）是标准结构
    """
    cfg, api_key, model = common.get_provider(provider)   # 从配置表取该平台信息
    # 用该平台的 key 和地址创建客户端（openai SDK 会把请求发到 base_url）
    client = OpenAI(api_key=api_key, base_url=cfg["base_url"])
    t = common.timer()                                     # 开始计时
    resp = client.chat.completions.create(
        model=model,
        messages=[
            # system：设定模型角色与行为（可对每个平台设置不同人格）
            {"role": "system", "content": "你是一个乐于助人的中文助手，回答简洁准确。"},
            # user：用户的真实问题
            {"role": "user", "content": prompt},
        ],
    )
    cost = common.elapsed(t)                               # 计时结束
    content = resp.choices[0].message.content              # 取回答正文
    # usage 对象里有计费关键数据：prompt_tokens（输入）/ completion_tokens（输出）
    usage = resp.usage
    return content, usage, cost


def main():
    """实验主流程：加载 key → 同时调用两个平台 → 打印结果与对比摘要。"""
    common.load_env()                                       # 1. 从 .env 读取 API key

    # 2. 命令行参数解析：python unified_call.py <provider1> <provider2>
    #    sys.argv = ["unified_call.py", "kimi", "mimo"]，argv[1:3] 取前两个平台名
    providers = sys.argv[1:3] if len(sys.argv) > 1 else ["kimi", "qwen"]

    # 3. 打开证据日志（之后的 log() 会同时写入终端和该文件）
    log_path = common.set_log_file("03_unified_call.txt")

    # 4. 打印实验头部信息（含运行时间与 Python 版本，满足任务书"记录环境版本"）
    common.log("=" * 72)
    common.log("实验 3：Python 统一调用脚本（多 provider 切换）")
    common.log(f"运行时间：{datetime.datetime.now().isoformat(timespec='seconds')}")
    common.log(f"Python    ：{sys.version.split()[0]}")
    common.log(f"证据文件  ：{log_path}")
    common.log("=" * 72)

    # 5. 定义"同一问题"——两个模型必须用完全一样的问题才有可比性
    prompt = "用一句话解释 HTTP 的 POST 方法与 JSON 请求体的关系。"
    common.log(f"\n统一任务问题：{prompt}")
    common.log(f"同时调用模型：{', '.join(providers)}")
    common.log("-" * 72)

    # 6. 逐个平台调用（try/except 保证一个平台失败不影响另一个）
    results = []
    for p in providers:
        try:
            content, usage, cost = call_one(p, prompt)
            # 把每个平台的调用结果逐项打印（模型名/地址/耗时/回答/用量）
            common.log(f"\n[provider] {p}")
            common.log(f"[model   ] {common.get_provider(p)[2]}")
            common.log(f"[base_url] {common.PROVIDERS[p]['base_url']}")
            common.log(f"[耗时    ] {cost:.2f} s")
            common.log(f"[响应内容] {content}")
            common.log(
                "[usage  ] prompt_tokens=%d, completion_tokens=%d, total_tokens=%d"
                % (usage.prompt_tokens, usage.completion_tokens, usage.total_tokens)
            )
            results.append({"provider": p, "content": content, "cost": cost,
                            "usage": usage})
        except Exception as e:
            # 失败也要记录（错误码/异常类型是实验 6 的素材）
            common.log(f"\n[provider] {p} 调用失败：{type(e).__name__}: {e}")

    # 7. 对比摘要：响应字数/耗时/token 用量并排展示，直观比较两平台
    common.log("\n" + "=" * 72)
    common.log("两模型对比摘要（响应长度 / 耗时 / token 用量）")
    common.log("-" * 72)
    for r in results:
        u = r["usage"]
        common.log(
            # :<6 左对齐占 6 格；:.2f 保留两位小数——让表格对齐好看
            f"{r['provider']:<6} 响应字数={len(r['content']):>4}  耗时={r['cost']:.2f}s  "
            f"prompt={u.prompt_tokens} completion={u.completion_tokens} total={u.total_tokens}"
        )
    common.close_log()                                      # 8. 关闭日志文件


# 标准入口：只有直接运行本脚本时才执行 main()
# （import 本文件时不会误触发实验，方便被其他脚本复用）
if __name__ == "__main__":
    main()
