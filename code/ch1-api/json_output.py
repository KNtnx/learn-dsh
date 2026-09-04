# -*- coding: utf-8 -*-
# =============================================================================
# json_output.py —— 第 1 章【实验 5：JSON 输出与校验】
#
# 真实工程场景：程序要消费模型输出时，必须让模型输出【结构化数据】，
#   而不是自由文本——这样才能 json.loads 解析成对象再处理。
#
# 本实验三步走：
#   1. 用 response_format={"type": "json_object"} 强制模型输出合法 JSON
#   2. 让模型按固定 schema 组织内容（课程计划：title/tasks/deadline/risks）
#   3. 用 Python json.loads 解析 + 逐字段校验（模拟程序侧消费）
#
# 用法：python json_output.py [provider]   （默认 kimi）
# 输出：终端 + evidence/ch1/05_json_output.txt（证据日志）
# =============================================================================
import sys
import json
import datetime

from openai import OpenAI
import common

# ---- 期望的结构（任务书要求的课程计划字段）----
# 键名是字段名，值是该字段的类型说明（字符串或字符串数组）
SCHEMA = {"title": "str", "tasks": "list[str]", "deadline": "str", "risks": "list[str]"}

# ---- 提示词：明确告诉模型四字段各自的类型与数量要求 ----
# 提示词写得越具体，模型越不容易"自由发挥"
PROMPT = (
    "请输出一个 JSON 对象，描述一个“学生大模型 API 调用教程”的课程计划。"
    "必须严格包含以下四个字段：\n"
    '1. "title"：字符串，教程标题；\n'
    '2. "tasks"：字符串数组，至少 3 个学习任务；\n'
    '3. "deadline"：字符串，截止日期；\n'
    '4. "risks"：字符串数组，至少 2 个可能的风险。\n'
    "只输出 JSON，不要输出任何其他文字。"
)


def validate(data):
    """按 SCHEMA 校验模型返回的 JSON，返回 (是否通过, 问题列表)。

    这就是"程序侧消费"的雏形：不只看"能不能解析"，还要看"字段类型对不对、
    数量够不够"——json.loads 只保证是合法 JSON，validate 保证是【我们需要的
    结构】。校验失败时把问题逐条报告，模拟真实 API 联调时的排错过程。
    """
    problems = []                                  # 收集所有问题（而不是遇到一个就停）
    if not isinstance(data, dict):
        return False, ["顶层不是 JSON 对象"]        # 比如模型输出了数组或字符串
    for field, typ in SCHEMA.items():
        if field not in data:
            problems.append(f"缺少字段 {field}")    # 字段缺失
        elif typ == "str" and not isinstance(data[field], str):
            problems.append(f"字段 {field} 不是字符串")
        elif typ == "list[str]":
            # 数组字段：先查是不是数组，再查元素是否都是字符串，最后查数量
            if not isinstance(data[field], list):
                problems.append(f"字段 {field} 不是数组")
            elif not all(isinstance(x, str) for x in data[field]):
                problems.append(f"字段 {field} 的元素不是字符串")
            elif field == "tasks" and len(data[field]) < 3:
                problems.append(f"字段 {field} 少于 3 项")
            elif field == "risks" and len(data[field]) < 2:
                problems.append(f"字段 {field} 少于 2 项")
    return len(problems) == 0, problems


def main():
    """实验主流程：加载 key → 强制 JSON 调用 → json.loads 校验 → 结构校验。"""
    common.load_env()
    provider = sys.argv[1] if len(sys.argv) > 1 else "kimi"

    # 打开证据日志（记录提示词、原始返回、校验结果全流程）
    log_path = common.set_log_file("05_json_output.txt")
    common.log("=" * 72)
    common.log("实验 5：JSON 输出与 json.loads 校验")
    common.log(f"运行时间：{datetime.datetime.now().isoformat(timespec='seconds')}")
    common.log(f"证据文件：{log_path}")
    common.log(f"provider：{provider}  model：{common.get_provider(provider)[2]}")
    common.log(f"期望 schema：{json.dumps(SCHEMA, ensure_ascii=False)}")
    common.log("=" * 72)

    common.log(f"\n提示词：\n{PROMPT}\n")

    # ---- 发起调用：response_format 是关键 ---- 
    # {"type": "json_object"} 告诉服务端"请只返回合法 JSON"，
    # 比在提示词里喊"请输出 JSON"可靠得多（服务端会做格式约束）
    cfg, api_key, model = common.get_provider(provider)
    client = OpenAI(api_key=api_key, base_url=cfg["base_url"])
    t = common.timer()
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "你只输出合法 JSON，不输出任何解释。"},
            {"role": "user", "content": PROMPT},
        ],
        response_format={"type": "json_object"},
    )
    cost = common.elapsed(t)

    raw = resp.choices[0].message.content     # 模型返回的原始文本（应是 JSON 字符串）
    usage = resp.usage                         # token 用量（计费参考）
    common.log(f"[原始返回]（耗时 {cost:.2f}s）：\n{raw}\n")

    # ---- 第 1 步校验：json.loads 能否解析 ----
    try:
        data = json.loads(raw)                 # 字符串 -> Python 对象
        common.log("[json.loads] 解析成功 ✓")
    except json.JSONDecodeError as e:
        # 解析失败：记录错误并结束（比如模型多说了句话导致不是纯 JSON）
        common.log(f"[json.loads] 解析失败 ✗：{e}")
        common.close_log()
        return

    # ---- 第 2 步校验：结构/类型/数量 ----
    ok, problems = validate(data)
    common.log(f"[结构校验] {'通过 ✓' if ok else '未通过 ✗'}")
    for p in problems:
        common.log(f"    - {p}")

    # ---- 展示解析后的对象（肉眼核对）+ 用量 ----
    common.log("\n[解析后的对象]")
    common.log(json.dumps(data, ensure_ascii=False, indent=2))
    common.log(
        "\n[usage] prompt=%d completion=%d total=%d"
        % (usage.prompt_tokens, usage.completion_tokens, usage.total_tokens)
    )
    common.close_log()


if __name__ == "__main__":
    main()
