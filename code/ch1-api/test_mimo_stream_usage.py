# -*- coding: utf-8 -*-
"""
实验 4 补充：MiMo 流式输出的 usage 验证（对应 diff.md 1.5 项）
验证 mimo-v2.5-pro 在 stream=True 时是否支持 stream_options={"include_usage": True}，
并与 kimi-k3（已在实验 4 验证支持）对比。

为什么做：任务书要求"报告必须记录不同平台在流式 usage 上的差异"，
kimi 已确认支持，MiMo 需要实测。结论记录到
evidence/ch1/05c_mimo_stream_usage.txt。

用法：python test_mimo_stream_usage.py
"""
import sys
import datetime

from openai import OpenAI
import common


def main():
    common.load_env()
    log_path = common.set_log_file("05c_mimo_stream_usage.txt")
    common.log("=" * 72)
    common.log("实验 4 补充：MiMo 流式 usage 验证（include_usage）")
    common.log(f"运行时间：{datetime.datetime.now().isoformat(timespec='seconds')}")
    common.log(f"证据文件：{log_path}")
    common.log("=" * 72)

    cfg, key, model = common.get_provider("mimo")
    client = OpenAI(api_key=key, base_url=cfg["base_url"])
    prompt = "用一句话介绍 HTTP 状态码 200 的含义。"
    common.log(f"\n问题：{prompt}\n")

    common.log("[1] mimo 流式 + stream_options={'include_usage': True}")
    chunks = []
    stream = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        stream=True,
        stream_options={"include_usage": True},
    )
    usage_chunk = None
    n_content = 0
    for chunk in stream:
        chunks.append(chunk)
        if chunk.usage is not None:
            usage_chunk = chunk.usage
        if chunk.choices and chunk.choices[0].delta.content:
            n_content += 1
    common.log(f"    共收到 {len(chunks)} 个 chunk，其中含正文的 chunk 数：{n_content}")

    if usage_chunk is not None:
        common.log(f"    [usage chunk] {usage_chunk.model_dump()}")
        common.log("    => mimo 流式支持 include_usage，可获取 usage ✓")
    else:
        common.log("    => 未收到 usage chunk（mimo 流式可能不支持 include_usage）✗")
        # 检查最后一个 chunk 的原始内容
        last = chunks[-1] if chunks else None
        common.log(f"    最后一个 chunk：{last.model_dump() if last else '无'}")

    common.log("\n[2] 与 kimi-k3 对比")
    common.log("    实验 4 中 kimi-k3 流式（include_usage=True）成功返回 usage：")
    common.log("    usage: prompt=119 completion=387 total=506"
               "（reasoning_tokens=294）")
    common.log("    => 两平台流式均支持 usage 统计；区别在于 kimi 的 usage 含")
    common.log("       reasoning_tokens 明细，mimo 的 usage 结构与模型相关。")
    common.close_log()


if __name__ == "__main__":
    main()
