# -*- coding: utf-8 -*-
"""
实验 5 补充：MiMo 的 JSON 输出行为验证
对比三种方式：
  A. 非流式 + response_format={"type":"json_object"}
  B. 非流式 + 无 response_format（仅提示词约束）
  C. 流式   + response_format={"type":"json_object"}（即 compare_models.py 中的失败场景）

为什么做：实验 7 中 MiMo 偶发输出 ```json 围栏导致解析失败——需要确认
这是"偶发表述偏好"（重试/换方式即可）还是"真的不支持"。
结论记录到 evidence/ch1/05b_mimo_json_behavior.txt。

用法：python test_mimo_json.py
"""
import sys
import json
import datetime

from openai import OpenAI
import common

PROMPT = (
    '请用 JSON 输出一个"学生 API 调用入门"的学习计划，包含字段：'
    '{"steps": [3 个步骤字符串], "common_errors": [2 个常见错误字符串], "advice": "一句建议"}。'
    "只输出 JSON，不要输出任何其他文字。"
)


def try_parse(raw):
    try:
        json.loads(raw)
        return True, ""
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:80]}"


def main():
    common.load_env()
    log_path = common.set_log_file("05b_mimo_json_behavior.txt")
    common.log("=" * 72)
    common.log("实验 5 补充：MiMo JSON 输出行为验证（三种方式对比）")
    common.log(f"运行时间：{datetime.datetime.now().isoformat(timespec='seconds')}")
    common.log(f"证据文件：{log_path}")
    common.log("=" * 72)

    cfg, key, model = common.get_provider("mimo")
    client = OpenAI(api_key=key, base_url=cfg["base_url"])
    msgs = [{"role": "user", "content": PROMPT}]

    # A. 非流式 + json_object
    common.log("\n[A] 非流式 + response_format=json_object")
    resp = client.chat.completions.create(
        model=model, messages=msgs, response_format={"type": "json_object"}
    )
    raw = resp.choices[0].message.content
    ok, err = try_parse(raw)
    common.log(f"    可解析: {ok}  {err}")
    common.log(f"    内容前 150 字符: {raw[:150]!r}")

    # B. 非流式 + 无 json_object
    common.log("\n[B] 非流式 + 仅提示词约束（无 response_format）")
    resp = client.chat.completions.create(model=model, messages=msgs)
    raw = resp.choices[0].message.content
    ok, err = try_parse(raw)
    common.log(f"    可解析: {ok}  {err}")
    common.log(f"    内容前 150 字符: {raw[:150]!r}")

    # C. 流式 + json_object（compare_models.py 中的失败场景）
    common.log("\n[C] 流式 + response_format=json_object")
    parts = []
    stream = client.chat.completions.create(
        model=model, messages=msgs, stream=True,
        response_format={"type": "json_object"},
    )
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            parts.append(chunk.choices[0].delta.content)
    raw = "".join(parts)
    ok, err = try_parse(raw)
    common.log(f"    可解析: {ok}  {err}")
    common.log(f"    内容前 150 字符: {raw[:150]!r}")

    common.log("\n[结论] 记录 MiMo 在不同方式下的 JSON 格式遵循表现，供报告对比分析。")
    common.close_log()


if __name__ == "__main__":
    main()
