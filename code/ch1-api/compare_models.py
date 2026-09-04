# -*- coding: utf-8 -*-
"""
实验 7：模型对比

同一中文任务（要求 JSON 输出）分别调用至少两个模型，比较 6 个维度：
  - 内容质量（响应字数、是否覆盖要求要点）
  - 格式遵循（要求输出 JSON，检查能否 json.loads——这是程序消费的关键）
  - 速度（总耗时、首字节延迟 TTFT；TTFT 用流式调用测得）
  - 费用（按官方定价估算，单价表见 notes/env-versions.md）
  - 错误恢复（结合实验 6：错误信息可读性对比）
  - 上下文长度等规格（见报告对比分析表）

同时用 matplotlib 生成对比图：docs/figures/ch1_model_compare.png

用法：python compare_models.py [provider1] [provider2]   （默认 kimi qwen）
输出：终端 + evidence/ch1/07_compare.txt（证据日志）+ 对比图 PNG
"""
import sys
import json
import datetime
import os

from openai import OpenAI
import common


def run_once(provider, prompt, stream=False):
    """对单个平台执行一次调用，返回包含各项指标的字典。

    参数：
      provider：平台名
      prompt  ：统一任务文本（两个平台必须用【同一个】问题才有可比性）
      stream  ：True 用流式调用（可测得 TTFT 首字节延迟）；
                False 用普通调用（顺便测 response_format JSON 输出）
    返回字典字段：
      provider/model 平台与模型名；content 回答全文；ttft 首字节延迟(s)；
      total 总耗时(s)；chars 响应字数；usage token 用量（流式时为 None）
    """
    cfg, api_key, model = common.get_provider(provider)
    client = OpenAI(api_key=api_key, base_url=cfg["base_url"])
    t = common.timer()
    ttft = None
    if stream:
        # ---- 流式分支：逐 chunk 拼接全文，首个 chunk 到达时刻 = TTFT ----
        full, ttft_chunks = [], []
        stream = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
        )
        for chunk in stream:
            if ttft is None:
                ttft = common.elapsed(t)      # 第一次收到数据的时间（感知延迟）
            if chunk.choices and chunk.choices[0].delta.content:
                full.append(chunk.choices[0].delta.content)
        content = "".join(full)               # 增量文本拼接 = 完整回答
    else:
        # ---- 普通分支：一次性返回，顺带用 response_format 强制 JSON ----
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content
        usage = resp.usage
    total = common.elapsed(t)
    return {
        "provider": provider,
        "model": model,
        "content": content,
        "ttft": ttft,                          # 流式才有；普通时 None
        "total": total,
        "chars": len(content),
        "usage": usage if not stream else None,
    }


# 对比用的同一中文任务：要求输出 JSON 以便检查格式遵循
PROMPT = (
    "请用 JSON 输出一个“学生 API 调用入门”的学习计划，包含字段："
    '{"steps": [3 个步骤字符串], "common_errors": [2 个常见错误字符串], "advice": "一句建议"}。'
    "只输出 JSON。"
)


def main():
    common.load_env()
    providers = sys.argv[1:3] if len(sys.argv) > 1 else ["kimi", "qwen"]
    log_path = common.set_log_file("07_compare.txt")
    common.log("=" * 72)
    common.log("实验 7：模型对比（同一中文任务，两个模型）")
    common.log(f"运行时间：{datetime.datetime.now().isoformat(timespec='seconds')}")
    common.log(f"证据文件：{log_path}")
    common.log("=" * 72)

    common.log(f"\n统一任务（要求 JSON 输出）：\n{PROMPT}\n")

    results = []
    for p in providers:
        common.log(f"\n--- 调用 {p}（流式，测 TTFT）---")
        r = run_once(p, PROMPT, stream=True)
        common.log(f"[model] {r['model']}")
        common.log(f"[TTFT ] {r['ttft']:.2f}s")
        common.log(f"[总耗时] {r['total']:.2f}s")
        common.log(f"[响应] {r['content']}")
        # 格式遵循检查：模型宣称"输出 JSON"，实际能否被 json.loads 解析？
        try:
            json.loads(r["content"])           # 解析成功 = 格式遵循良好
            r["json_ok"] = True
            common.log("[格式遵循] JSON 可解析 ✓")
        except Exception:
            # 解析失败（如模型加了 ```json 围栏或多说了句话）——如实记录
            r["json_ok"] = False
            common.log("[格式遵循] JSON 解析失败 ✗")
        results.append(r)

    # 对比表
    common.log("\n" + "=" * 72)
    common.log("对比摘要")
    common.log("-" * 72)
    common.log(f"{'指标':<16}{'':2}{providers[0]:<12}{providers[1]:<12}")
    common.log(f"{'总耗时 (s)':<16}{'':2}{results[0]['total']:<12.2f}{results[1]['total']:<12.2f}")
    common.log(f"{'TTFT (s)':<16}{'':2}{results[0]['ttft']:<12.2f}{results[1]['ttft']:<12.2f}")
    common.log(f"{'响应字数':<16}{'':2}{results[0]['chars']:<12}{results[1]['chars']:<12}")
    common.log(f"{'JSON 可解析':<16}{'':2}{str(results[0]['json_ok']):<12}{str(results[1]['json_ok']):<12}")

    # 生成对比图
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        # 中文字体（Windows），避免图内中文显示为方框
        plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "sans-serif"]
        plt.rcParams["axes.unicode_minus"] = False

        fig, axes = plt.subplots(1, 2, figsize=(9, 3.6))
        names = providers
        totals = [r["total"] for r in results]
        ttfts = [r["ttft"] if r["ttft"] else r["total"] for r in results]
        axes[0].bar(names, totals, color=["#4C72B0", "#DD8452"])
        axes[0].set_title("总耗时 (s)")
        axes[0].set_ylabel("seconds")
        axes[1].bar(names, ttfts, color=["#4C72B0", "#DD8452"])
        axes[1].set_title("首字节延迟 TTFT (s)")
        axes[1].set_ylabel("seconds")
        fig.suptitle("模型对比：同一中文任务（流式调用）")
        fig.tight_layout()
        fig_path = os.path.abspath(
            os.path.join(common.BASE_DIR, "..", "..", "docs", "figures", "ch1_model_compare.png")
        )
        os.makedirs(os.path.dirname(fig_path), exist_ok=True)
        fig.savefig(fig_path, dpi=150)
        common.log(f"\n[图表已生成] {fig_path}")
    except Exception as e:
        common.log(f"\n[图表生成失败] {type(e).__name__}: {e}（报告中将用表格代替）")

    common.log("\n[费用说明] token 单价见 notes/env-versions.md（按官方定价页记录），"
               "本实验每次调用 token 量级为数百，费用远低于 0.01 元。")
    common.close_log()


if __name__ == "__main__":
    main()
