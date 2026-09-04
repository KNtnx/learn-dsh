# -*- coding: utf-8 -*-
"""
calc_cost.py —— 实验费用核算（报告"费用记录"评分点）

做什么：读取 evidence/ch1/ 中各实验日志里【真实返回的 token 用量】，
        乘以【官方单价】算出每次调用的费用，并汇总全章总费用。

为什么：任务书要求"费用记录"。只写"很便宜"不算记录——要用
        官方定价 × 真实 usage 给出可核算的数字（与平台账单可对账）。

官方单价（每 1M tokens，人民币，访问日期 2026-08-18）：
  kimi-k3       输入(缓存未命中) ¥20.00 / 输入(缓存命中) ¥2.00 / 输出 ¥100.00
                （来源：https://platform.kimi.com/docs/pricing/chat-k3.md）
  mimo-v2.5-pro 输入(缓存未命中) ¥3.00 / 输入(缓存命中) ¥0.025 / 输出 ¥6.00
                （来源：https://mimo.mi.com/static/docs/price/pay-as-you-go.md）

公式：费用(元) = prompt_tokens × 输入单价 / 1e6 + completion_tokens × 输出单价 / 1e6
      （除以 1e6 是因为单价按"每 1M tokens"计价）
口径：默认按缓存未命中（保守）；若日志中检测到 cached_tokens，额外给缓存命中口径。

用法：python calc_cost.py
输出：终端 + evidence/ch1/08_cost_summary.txt（费用汇总表）
"""
import os
import re
import json
import datetime

import common

# ---- 官方单价表（单位：元 / 每 1M tokens）----
# in_miss：输入且未命中缓存；in_hit：输入命中缓存（更便宜）；out：输出
PRICES = {
    "kimi": {"in_miss": 20.0, "in_hit": 2.0, "out": 100.0},
    "mimo": {"in_miss": 3.0, "in_hit": 0.025, "out": 6.0},
}

# 证据日志目录（工作区根/evidence/ch1），与 common.py 的约定一致
EVIDENCE_DIR = os.path.abspath(
    os.path.join(common.BASE_DIR, "..", "..", "evidence", "ch1")
)


def split_provider_segments(text):
    """按 "[provider] xxx" 标记把日志文本切成段，返回 [(平台名, 该平台段落), ...]。

    为什么需要分段：unified_call.py / compare_models.py 的日志里同一个文件
    有多个平台的调用记录，费用必须按平台分别核算（单价不同），
    所以先用 [provider] 标记把日志内容切到各自平台名下。
    没有标记（如单平台实验日志）时返回 [("unknown", 全文)]，由调用方指定平台。
    """
    parts = re.split(r"\[provider\]\s+(\w+)", text)
    if len(parts) == 1:
        return [("unknown", parts[0])]
    result = []
    for i in range(1, len(parts), 2):
        result.append((parts[i], parts[i + 1]))
    return result


def extract_usage(segment):
    """从段文本提取 (prompt, completion, cached)；支持多种打印格式。"""
    # 格式 A: prompt_tokens=X, completion_tokens=Y（任意顺序、带引号 JSON 亦可）
    m = re.search(
        r'prompt_tokens["\']?[=:]\s*(\d+).{0,150}?completion_tokens["\']?[=:]\s*(\d+)',
        segment, re.S)
    if m:
        return int(m.group(1)), int(m.group(2)), 0
    m = re.search(
        r'completion_tokens["\']?[=:]\s*(\d+).{0,150}?prompt_tokens["\']?[=:]\s*(\d+)',
        segment, re.S)
    if m:
        return int(m.group(2)), int(m.group(1)), 0
    # 格式 B: prompt=X completion=Y（如 json_output）
    m = re.search(r"prompt[=:]\s*(\d+)\s+completion[=:]\s*(\d+)", segment)
    if m:
        return int(m.group(1)), int(m.group(2)), 0
    return None


def find_cached(segment):
    """从段文本提取 cached_tokens（上下文缓存命中的 token 数）。

    注意：键名后要容忍引号——JSON 原始响应里是 "cached_tokens":100
    （键加引号），而 Python 脚本打印的是 cached_tokens=100（无引号），
    所以用 ["']? 两种都覆盖（与 extract_usage 的处理方式一致）。
    返回值 0 表示"未检测到缓存命中"（按缓存未命中保守口径计价）。
    """
    m = re.search(r'cached_tokens["\']?[=:]\s*(\d+)', segment)
    return int(m.group(1)) if m else 0


def cost(provider, prompt, completion, cached=0):
    p = PRICES[provider]
    miss = prompt * p["in_miss"] / 1e6 + completion * p["out"] / 1e6
    hit = None
    if cached:
        hit = cached * p["in_hit"] / 1e6 \
            + (prompt - cached) * p["in_miss"] / 1e6 \
            + completion * p["out"] / 1e6
    return miss, hit


def main():
    log_path = common.set_log_file("08_cost_summary.txt")
    common.log("=" * 72)
    common.log("费用汇总：官方单价 × 各实验真实 usage")
    common.log(f"运行时间：{datetime.datetime.now().isoformat(timespec='seconds')}")
    common.log(f"证据文件：{log_path}")
    common.log("=" * 72)

    common.log("\n[官方单价]（每 1M tokens，人民币，访问日期 2026-08-18）")
    common.log("  kimi-k3       ：输入 ¥20.00（缓存命中 ¥2.00）/ 输出 ¥100.00")
    common.log("                 https://platform.kimi.com/docs/pricing/chat-k3.md")
    common.log("  mimo-v2.5-pro ：输入 ¥3.00（缓存命中 ¥0.025）/ 输出 ¥6.00")
    common.log("                 https://mimo.mi.com/static/docs/price/pay-as-you-go.md")
    common.log("\n[公式] 费用(元) = prompt×输入单价/1e6 + completion×输出单价/1e6")
    common.log("        （默认按缓存未命中保守口径；检测到缓存时另给命中口径）")

    # (标签, 文件名, 固定 provider 或 None=按 [provider] 分段)
    files = [
        ("实验 3 统一调用", "03_unified_call.txt", None),
        ("实验 4 流式", "04_stream.txt", "kimi"),
        ("实验 5 JSON", "05_json_output.txt", "kimi"),
        ("实验 7 模型对比", "07_compare.txt", None),
    ]
    curl_files = [
        ("实验 2 curl Kimi（完整）", "02_curl_kimi_full.txt", "kimi"),
        ("实验 2 curl Kimi（截断）", "02_curl_kimi.txt", "kimi"),
        ("实验 2 curl MiMo（完整）", "02_curl_mimo_full.txt", "mimo"),
        ("实验 2 curl MiMo（截断）", "02_curl_mimo.txt", "mimo"),
    ]
    total_miss = {"kimi": 0.0, "mimo": 0.0}
    total_hit = {"kimi": 0.0, "mimo": 0.0}

    common.log("\n" + "-" * 72)
    common.log(f"{'实验/调用':<26}{'prompt':>8}{'completion':>12}{'cached':>8}"
               f"{'费用(未命中)':>14}{'费用(命中)':>14}")
    common.log("-" * 72)

    def report_row(label, provider, prompt, completion, cached):
        miss, hit = cost(provider, prompt, completion, cached)
        total_miss[provider] += miss
        if hit:
            total_hit[provider] += hit
        hit_s = f"{hit:.6f}" if hit else "-"
        common.log(f"{label:<26}{prompt:>8}{completion:>12}{cached:>8}"
                   f"{miss:>14.6f}{hit_s:>14}")

    for label, fn, fixed_provider in files:
        path = os.path.join(EVIDENCE_DIR, fn)
        if not os.path.exists(path):
            common.log(f"{label:<26} 缺少日志 {fn}")
            continue
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        segments = split_provider_segments(text)
        for provider, seg in segments:
            provider = fixed_provider or provider
            if provider == "unknown":
                continue
            usage = extract_usage(seg)
            if usage is None:
                common.log(f"{label + '/' + provider:<26} 未找到 usage"
                           f"（该调用未打印 usage，如实验 7 流式）")
                continue
            prompt, completion, _ = usage
            cached = find_cached(seg)
            report_row(f"{label}/{provider}", provider, prompt, completion, cached)

    for label, fn, provider in curl_files:
        path = os.path.join(EVIDENCE_DIR, fn)
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        usage = extract_usage(text)
        if usage is None:
            continue
        prompt, completion, _ = usage
        cached = find_cached(text)
        report_row(label, provider, prompt, completion, cached)

    common.log("-" * 72)
    for provider in ("kimi", "mimo"):
        common.log(f"{provider + ' 合计(未命中)':<26}{'':>28}"
                   f"{total_miss[provider]:>14.6f} 元")
        if total_hit[provider]:
            # 注意：该合计只累计"检测到缓存命中"的行（其余行按未命中计）
            common.log(f"{provider + ' 合计(含命中,仅命中行)':<26}{'':>28}"
                       f"{total_hit[provider]:>14.6f} 元")
    grand = total_miss["kimi"] + total_miss["mimo"]
    common.log(f"\n[结论] 第 1 章 API 调用总费用（未命中保守口径）≈ "
               f"{grand:.4f} 元；若计入上下文缓存命中，费用更低。")
    common.log("  注：实验 6 错误处理不产生计费 token（请求均被拒绝）；")
    common.log("      实验 7 流式调用未打印 usage，未计入；其量级与实验 3 相当。")
    common.log("      实际账单以平台控制台为准，本表为按官方单价的估算。")
    common.close_log()


if __name__ == "__main__":
    main()
