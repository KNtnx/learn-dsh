# -*- coding: utf-8 -*-
"""
test_tutorial.py —— 教程产出的独立测试脚本（harness 的"测试"面）

用法（由模型通过 run_tests 工具触发，也可手动）：
  python tests/test_tutorial.py <tutorial.json 路径>

设计（任务书 harness 层：脚本 + 测试 + JSON 校验 + 评分 rubrics）：
  测试脚本是独立于模型的代码——模型写出 tutorial.json 后由它判定，
  结论（每项 通过/失败 + 汇总）回传给模型，模型无法自评。
  检查项 = JSON 结构（五字段） + rubric 八项要点 + 引用格式。

安全：只读检查，不执行教程内容、不联网。
"""
import json
import re
import sys
import pathlib

# ---- rubric 八项（与 rubric.py 同一套标准）----
RUBRIC = [
    ("前置条件", ["注册", "申请", "key 获取", "账号"]),
    ("API key 安全", ["环境变量", "泄露", "安全", "脱敏", "不提交"]),
    ("错误处理", ["401", "429", "错误", "状态码", "限流", "重试"]),
    ("可复现步骤", ["步骤", "命令", "复制", "运行", "示例"]),
    ("示例代码", ["代码", "curl", "python", "脚本", "SDK"]),
    ("费用说明", ["费用", "价格", "计费", "token 用量", "免费额度"]),
    ("参考链接", ["http", "文档", "官网", "链接", "platform."]),
    ("进阶能力", ["流式", "stream", "JSON", "结构化输出", "多轮"]),
]

REQUIRED_FIELDS = ["title", "steps", "safety_notes", "error_handling", "references"]
STRUCT_TYPES = {
    "title": str,
    "steps": list,
    "safety_notes": list,
    "error_handling": list,
    "references": list,
}


def run_tests(path: str):
    """对 path 指向的 JSON 执行全部检查，返回 (通过数, 总项数, 逐项结果列表)。"""
    results = []   # (项目名, 是否通过, 说明)

    # ① 文件存在且合法 JSON
    fp = pathlib.Path(path)
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
        results.append(("JSON 合法性", True, "json.loads 解析成功"))
    except Exception as e:
        print(f"FAIL JSON 合法性：{e}")
        return 0, 1, [("JSON 合法性", False, str(e))]

    # ② 五字段齐全、类型正确（这是第 3 层实验的 schema 契约）
    for f in REQUIRED_FIELDS:
        ok = f in data and isinstance(data[f], STRUCT_TYPES[f]) and len(data[f]) > 0
        results.append((f"字段 {f}", ok, "类型正确且非空" if ok else "缺失或类型错误/为空"))

    # ③ rubric 八项要点（拼接所有文本后做关键词检查——与 rubric.py 一致）
    text = json.dumps(data, ensure_ascii=False)
    for name, kws in RUBRIC:
        ok = any(kw.lower() in text.lower() for kw in kws)
        results.append((f"rubric {name}", ok, "关键词命中" if ok else "未命中任何关键词"))

    # ④ 引用格式：references 每条应含 https:// 与"访问日期"字样
    refs = data.get("references", [])
    n = len(refs)
    with_url = sum(1 for r in refs if "http" in str(r))
    with_date = sum(1 for r in refs if "访问日期" in str(r))
    ok = n > 0 and with_url == n and with_date == n
    results.append(("引用格式", ok, f"{with_url}/{n} 条含 URL，{with_date}/{n} 条含访问日期"))

    # ④b 引用日期真实性提示（尽力而为：标注"编造风险"，不作为硬失败）
    fake_dates = [str(r) for r in refs if re.search(r"20(1[0-9]|2[0-9])[-/年]", str(r))]
    if fake_dates:
        results.append(("日期标注", True, "存在具体日期（真伪需人工核对，见报告分析）"))

    passed = sum(1 for _, p, _ in results if p)
    total = len(results)
    return passed, total, results


def main():
    if len(sys.argv) < 2:
        print("用法：python test_tutorial.py <tutorial.json>")
        return 1
    passed, total, results = run_tests(sys.argv[1])
    for name, ok, note in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}: {note}")
    print(f"\n== 测试汇总：{passed}/{total} 项通过 ==")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
