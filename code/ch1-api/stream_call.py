# -*- coding: utf-8 -*-
# =============================================================================
# stream_call.py —— 第 1 章【实验 4：流式输出（stream=True）】
#
# 流式输出是什么（通俗版）：
#   普通输出 = 餐厅做好一整桌菜再端上来（等全部生成完才看到结果）
#   流式输出 = 边做边端（每个 token 生成完立刻推给客户端，像打字机）
# 技术本质：SSE（Server-Sent Events）长连接，服务器逐个 chunk 推送。
#
# 本脚本做两件事：
#   1. 流式调用：逐 chunk 打印结构（delta.content 增量文本），找出
#      "首字节延迟 TTFT"（拿到第一个字节的时间）
#   2. 普通调用对照：比较两种方式的总耗时与返回内容
#
# 用法：python stream_call.py [provider]   （默认 kimi）
# 输出：终端 + evidence/ch1/04_stream.txt（证据日志，chunk 结构全记录）
# =============================================================================
import sys
import datetime

from openai import OpenAI
import common


def stream_call(provider: str, prompt: str):
    """流式调用：逐个打印 chunk 结构，返回 (完整文本, usage, TTFT, 总耗时, chunk 数)。

    关键观察点：
      - 每个 chunk 的 choices[0].delta.content 是【增量】文本（不是全文）
      - 推理模型（如 kimi-k3）前段 chunk 的 delta.content 是 None（模型在思考）
      - 流末尾可能有一个专属 chunk 携带 usage（token 用量）
    """
    cfg, api_key, model = common.get_provider(provider)
    client = OpenAI(api_key=api_key, base_url=cfg["base_url"])

    chunks = []                    # 收集全部 chunk，用于最后拼接与统计
    first_byte_cost = None         # TTFT：第一个 chunk 到达的时间（含思考开始）
    t = common.timer()

    # stream=True 告诉 SDK：我要流式响应，请在生成过程中逐块返回
    # stream_options={"include_usage": True}：请求在流末尾额外返回 usage 块
    stream = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "你是一个简洁的中文助手。"},
            {"role": "user", "content": prompt},
        ],
        stream=True,
        stream_options={"include_usage": True},
    )

    # 逐个消费 chunk（for 循环会阻塞等待下一个 chunk，直到流结束）
    for chunk in stream:
        # 第一个 chunk 到达的时刻 = 首字节延迟（客户端开始"看到东西"的时间）
        if first_byte_cost is None:
            first_byte_cost = common.elapsed(t)
        chunks.append(chunk)

        # 有的 chunk 没有 choices（用空 choices 携带 usage 元数据），要单独处理
        choice = chunk.choices[0] if chunk.choices else None
        if choice is None:
            if chunk.usage is not None:
                common.log(f"[usage chunk] {chunk.usage.model_dump()}")
            continue

        # 核心结构展示：chunk id + 结束原因 + 增量文本
        # delta.content 为 None 表示"当前没有生成正文"（推理模型思考中）
        delta = choice.delta
        common.log(
            f"chunk id={chunk.id}  finish_reason={choice.finish_reason}  "
            f"delta.content={delta.content!r}"
        )

    total_cost = common.elapsed(t)

    # 汇总：把所有 chunk 的增量文本拼起来 = 完整回答（delta.content 逐个累加）
    full_text = "".join(
        c.choices[0].delta.content or ""
        for c in chunks
        if c.choices and c.choices[0].delta and c.choices[0].delta.content
    )
    usage = None
    # 在所有 chunk 里找 usage（流末尾专门携带的那个块）
    for c in chunks:
        if c.usage is not None:
            usage = c.usage
            break
    return full_text, usage, first_byte_cost, total_cost, len(chunks)


def plain_call(provider: str, prompt: str):
    """普通（非流式）调用，作为对照组：必须等模型生成完整回答才返回。"""
    cfg, api_key, model = common.get_provider(provider)
    client = OpenAI(api_key=api_key, base_url=cfg["base_url"])
    t = common.timer()
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "你是一个简洁的中文助手。"},
            {"role": "user", "content": prompt},
        ],
    )
    # 普通调用没有"首字节"概念：一次性拿到完整内容
    return resp.choices[0].message.content, common.elapsed(t)


def main():
    """实验主流程：流式调用（打印 chunk 结构）→ 普通调用对照 → 结论。"""
    common.load_env()
    provider = sys.argv[1] if len(sys.argv) > 1 else "kimi"
    log_path = common.set_log_file("04_stream.txt")
    common.log("=" * 72)
    common.log("实验 4：流式输出（stream=True）")
    common.log(f"运行时间：{datetime.datetime.now().isoformat(timespec='seconds')}")
    common.log(f"证据文件：{log_path}")
    common.log(f"provider：{provider}  model：{common.get_provider(provider)[2]}")
    common.log("=" * 72)

    prompt = "请用三句话介绍流式输出（streaming）在 LLM API 中的作用。"
    common.log(f"\n问题：{prompt}\n")

    # ---- 第 1 部分：流式调用 ----
    common.log("[1] 流式调用开始，逐 chunk 打印（注意 delta.content 为增量文本）：")
    common.log("-" * 72)
    full_text, usage, first_byte, total, n_chunks = stream_call(provider, prompt)
    common.log("-" * 72)
    common.log(f"[流式] 共 {n_chunks} 个 chunk")
    common.log(f"[流式] 首字节延迟（TTFT）={first_byte:.2f}s，总耗时={total:.2f}s")
    common.log(f"[流式] 完整内容：{full_text}")
    if usage:
        common.log(
            "[流式] usage: prompt=%d completion=%d total=%d"
            % (usage.prompt_tokens, usage.completion_tokens, usage.total_tokens)
        )

    # ---- 第 2 部分：普通调用对照 ----
    common.log("\n[2] 普通（非流式）调用对照：")
    common.log("-" * 72)
    plain_text, plain_cost = plain_call(provider, prompt)
    common.log(f"[普通] 总耗时={plain_cost:.2f}s（需等待完整响应生成完毕）")
    common.log(f"[普通] 内容：{plain_text}")

    # ---- 第 3 部分：结论 ----
    common.log("\n[3] 结论：")
    common.log(
        "流式输出在首个 token 到达后即可开始渲染（TTFT 显著小于总耗时），"
        "普通输出必须等完整响应；两者最终内容一致，token 用量相同。"
    )
    common.close_log()


if __name__ == "__main__":
    main()
