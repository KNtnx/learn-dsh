# -*- coding: utf-8 -*-
"""
第 2 章实验：同一任务四层递进（Prompt→Context→Harness→Loop）

核心思想（任务书第二章）：
  同一个任务"写一份学生 API 调用教程"，逐层增加约束与循环，
  观察每一层带来什么变化：
    第 1 层 Prompt  ：只给一句话任务（模型自由发挥）
    第 2 层 Context ：加入上下文包（官方文档摘要/学生基础/模板要求）
    第 3 层 Harness ：强制 JSON 结构 + 真实校验器（json.loads + rubric 八项）
    第 4 层 Loop    ：把校验器接进循环——未通过项反馈给模型修改，直到通过

模型选择：mimo-v2.5（输入 ¥1/M、输出 ¥2/M，访问日期 2026-08-18；
价格仅为 kimi-k3（输出 ¥100/M）的 1/50，pro 档的 1/3，
四层实验多轮调用用非 pro 档成本最低，性价比最高。

证据：每层完整保留"提示词/输出/校验结果"到 evidence/ch2/02_layers.txt。

用法：
  python layers.py             # 跑全部四层
  python layers.py 2           # 只跑第 1、2 层
  python layers.py 4 3         # 从第 3 层续跑（断点续跑，日志追加）
"""
import sys
import os
import json
import re
import datetime

from openai import OpenAI
import common_ch2
from rubric import check, format_rubric
from harness_tools import ToolAgent, SANDBOX

# 四层共用的统一任务（每层必须用同一任务，否则没有对比意义）
TASK = "写一个面向零基础学生的\"大模型 API 调用入门教程\"。"

# ---- 第 2 层使用的上下文包（真实材料摘要，非编造）----
CONTEXT_PACK = """【官方文档摘要：Kimi API 快速开始】
- 申请：platform.moonshot.cn 注册后创建 API Key（sk- 开头）；
- 调用：POST https://api.moonshot.cn/v1/chat/completions，
  Header 带 Content-Type: application/json 与 Authorization: Bearer <KEY>；
- 请求体：model、messages（role: system/user/assistant）、temperature、max_tokens；
- 模型 kimi-k3 是推理模型，max_tokens 需预留推理 token，建议 >=1000；
- 计费按 token（输入/输出分开），具体单价见官方定价页。

【OpenAI-compatible 迁移说明】
国内平台（Kimi/MiMo/火山方舟/Qwen）大多兼容 OpenAI 协议，同一段代码
只需替换 base_url、api_key、model。

【学生基础】
- 已学 HTTP 基础（POST、Header、JSON），会用 Python 写简单脚本；
- 从未调用过任何大模型 API，不知道 API key 是什么。

【报告模板要求】
教程应包含：背景说明、环境准备、实验步骤、结果、对比分析、参考资料；
参考资料需标题+URL+访问日期。"""

# ---- 第 3/4 层：harness 约束 ----
HARNESS_RULE = (
    "你必须以 JSON 对象输出教程，结构为："
    '{"title": str, "steps": [str...], "safety_notes": [str...], '
    '"error_handling": [str...], "references": [str...]}。'
    "只输出 JSON，不要输出任何其他文字。"
)


# ---- 实验模型：mimo-v2.5（非 pro 档，输入 ¥1/M、输出 ¥2/M，最省钱；见 common_ch2.PROVIDERS）----
MODEL = "mimo-v2.5"


def call_model(client, messages, layer_name, log):
    """流式调用（更稳，避免 read timeout 挂起）。"""
    t = common_ch2.timer_start()
    stream = client.chat.completions.create(
        model=MODEL, messages=messages, stream=True,
        stream_options={"include_usage": True},
    )
    parts = []
    usage = None
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            parts.append(chunk.choices[0].delta.content)
        if chunk.usage is not None:
            usage = chunk.usage
    cost = common_ch2.timer_end(t)
    content = "".join(parts)
    log(f"[{layer_name}] 耗时 {cost:.1f}s | usage: prompt={usage.prompt_tokens} "
        f"completion={usage.completion_tokens}" if usage else f"[{layer_name}] 耗时 {cost:.1f}s")
    return content, usage


def main():
    # 参数1：总层数；参数2：起始层（断点续跑）
    layers = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    start = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    common_ch2.load_env()
    log_path = common_ch2.set_log_file("02_layers.txt", append=(start > 1))
    if start <= 1:
        common_ch2.log("=" * 70)
        common_ch2.log("第 2 章实验：同一任务四层递进（Prompt→Context→Harness→Loop）")
        common_ch2.log(f"模型：{MODEL}（mimo-v2.5，经 PROVIDERS 配置统一切换）")
        common_ch2.log(f"运行时间：{datetime.datetime.now().isoformat(timespec='seconds')}")
        common_ch2.log(f"任务：{TASK}")
        common_ch2.log(f"证据文件：{log_path}")
        common_ch2.log("=" * 70)

    client = OpenAI(
        api_key=os.environ.get(common_ch2.PROVIDERS["mimo"]["env"], ""),
        base_url=common_ch2.PROVIDERS["mimo"]["base_url"],
        timeout=180,
        max_retries=2,
    )
    model = common_ch2.PROVIDERS["mimo"]["model"]

    # ---------- 第 1 层：Prompt ----------
    if layers >= 1 and start <= 1:
        common_ch2.log("\n" + "=" * 70)
        common_ch2.log("第 1 层：Prompt（只给一句任务，无任何额外信息）")
        common_ch2.log("=" * 70)
        common_ch2.log(f"用户消息：{TASK}")
        content, _ = call_model(
            client,
            [{"role": "user", "content": TASK}],
            "Prompt",
            common_ch2.log,
        )
        common_ch2.log(f"\n[输出]\n{content}")
        missed = check(content)
        common_ch2.log(f"\n[rubric 检查] 未覆盖要点：{missed if missed else '全部覆盖'}")
        common_ch2.log(f"[要点覆盖] {8 - len(missed)}/8")

    # ---------- 第 2 层：Context ----------
    if layers >= 2 and start <= 2:
        common_ch2.log("\n" + "=" * 70)
        common_ch2.log("第 2 层：Context（加入上下文包：文档摘要/示例/学生基础/模板）")
        common_ch2.log("=" * 70)
        ctx_messages = [
            {"role": "system", "content": "你是教程撰写助手。请基于提供的资料撰写，"
             "不要编造文档中没有的细节。"},
            {"role": "user", "content": TASK + "\n\n【资料】\n" + CONTEXT_PACK},
        ]
        content, _ = call_model(client, ctx_messages, "Context", common_ch2.log)
        common_ch2.log(f"\n[输出]\n{content}")
        missed = check(content)
        common_ch2.log(f"\n[rubric 检查] 未覆盖要点：{missed if missed else '全部覆盖'}")
        common_ch2.log(f"[要点覆盖] {8 - len(missed)}/8")

    # ---------- 第 3 层：Harness（工具 + 脚本 + 测试） ----------
    if layers >= 3 and start <= 3:
        common_ch2.log("\n" + "=" * 70)
        common_ch2.log("第 3 层：Harness（真实工具集：写入/测试/bash——模型可执行，不自动迭代）")
        common_ch2.log("=" * 70)
        common_ch2.log("工具：write_file / run_tests / bash（改编自 learn-claude-code "
                       "agents/s01_agent_loop.py + s02_tool_use.py 的工具循环模式）")
        common_ch2.log("测试：tests/test_tutorial.py（JSON 五字段 + rubric 八项 + 引用格式）")
        common_ch2.log("安全边界：只允许写入 sandbox（evidence/ch2/sandbox），bash 黑名单")
        # 清空沙箱：每次实验从零开始（模型上次的产出不残留下次）
        SANDBOX.mkdir(parents=True, exist_ok=True)
        for f in SANDBOX.iterdir():
            if f.is_file():
                f.unlink()
        agent = ToolAgent(client, MODEL, common_ch2.log)
        harness_messages = [
            {"role": "system", "content":
             "你是教程撰写代理。你拥有三个工具：write_file（写入 sandbox 文件）、"
             "run_tests（对 sandbox/tutorial.json 运行测试脚本，返回逐项结果）、"
             "bash（执行命令）。流程：用 write_file 把教程按 JSON 结构写入 "
             "tutorial.json，然后用 run_tests 验证；根据测试结果决定是否修正一次。"},
            {"role": "user", "content": TASK + "\n\n【资料】\n" + CONTEXT_PACK
             + "\n\n【输出约束】\n" + HARNESS_RULE},
        ]
        final = agent.run(harness_messages, max_tool_turns=2)
        # 提取最后一次测试报告（harness 的验证结论由测试脚本给出，非模型自评）
        test_out = [m for m in harness_messages
                    if m.get("role") == "tool" and "测试汇总" in str(m.get("content", ""))]
        last_test = test_out[-1]["content"] if test_out else "(模型未运行测试)"
        common_ch2.log(f"\n[harness 测试结果]\n{last_test}")
        common_ch2.log(f"\n[模型最终答复]\n{final}")

    # ---------- 第 4 层：Loop agent（检查器接入循环，失败注入反馈） ----------
    if layers >= 4 and start <= 4:
        common_ch2.log("\n" + "=" * 70)
        common_ch2.log("第 4 层：Loop agent（计划-执行-读测试-修改-再验证，直到清单通过）")
        common_ch2.log("=" * 70)
        max_rounds = 4
        SANDBOX.mkdir(parents=True, exist_ok=True)
        for f in SANDBOX.iterdir():
            if f.is_file():
                f.unlink()
        agent = ToolAgent(client, MODEL, common_ch2.log)
        loop_base = [
            {"role": "system", "content":
             "你是教程撰写代理。你拥有三个工具：write_file（写入 sandbox 文件）、"
             "run_tests（对 sandbox/tutorial.json 运行测试脚本）、bash（执行命令）。"
             "流程：用 write_file 把教程按 JSON 结构写入 tutorial.json，用 run_tests "
             "验证；测试未全部通过时，根据失败项修改后再验证，直到通过。"},
        ]
        final = ""
        for rnd in range(1, max_rounds + 1):
            common_ch2.log(f"\n--- 第 {rnd} 轮 ---")
            if rnd == 1:
                user_msg = TASK + "\n\n【资料】\n" + CONTEXT_PACK \
                    + "\n\n【输出约束】\n" + HARNESS_RULE
            else:
                user_msg = (
                    f"上一轮测试未通过以下检查项：{', '.join(missed_items)}。"
                    "请修改 tutorial.json 后重新运行测试，直到全部通过。"
                )
            messages = loop_base + [{"role": "user", "content": user_msg}]
            final = agent.run(messages, max_tool_turns=12)
            # 从工具结果中解析本轮测试汇总（X/Y）
            test_out = [m for m in messages
                        if m.get("role") == "tool" and "测试汇总" in str(m.get("content", ""))]
            if not test_out:
                common_ch2.log("[检查] 本轮未见测试报告（模型未运行 run_tests）")
                missed_items = ["测试未执行"]
                continue
            summary = test_out[-1]["content"]
            m = re.search(r"== 测试汇总：(\d+)/(\d+) 项通过 ==", str(summary))
            passed, total = (int(m.group(1)), int(m.group(2))) if m else (0, 1)
            common_ch2.log(f"\n[本轮测试]\n{summary}")
            if passed == total:
                common_ch2.log(f"[完成] 第 {rnd} 轮通过全部 {total} 项测试！")
                common_ch2.log(f"\n[最终输出]\n{final}")
                break
            # 提取未通过项，作为下一轮反馈
            missed_items = [ln.split("FAIL  ", 1)[-1].split(":", 1)[0]
                            for ln in str(summary).splitlines() if ln.startswith("FAIL")]
            common_ch2.log(f"[未通过] {missed_items}（将作为第 {rnd + 1} 轮反馈）")
        else:
            common_ch2.log(f"[终止] 达到 {max_rounds} 轮上限仍未全部通过")

    # 结束标记：capture 脚本以它判断"实验真正完成"（模型等待期间日志会停住，
    # 不能用"日志行数不变"来判断完成——否则会误杀正在运行的窗口）。
    common_ch2.log("\n[END] 四层实验完成（全部层已运行完毕）")
    common_ch2.close_log()


if __name__ == "__main__":
    main()
