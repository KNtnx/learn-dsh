# ch2-evolution —— 第 2 章：提示词到智能体的演化

## 内容

- 同一任务四层递进实验：**Prompt**（只给一句话）→ **Context**（上下文包）→ **Harness**（JSON 结构+校验器）→ **Loop**（rubric 反馈循环）
- 概念图：四层嵌套演化示意图（生成脚本已移至 `scripts/make_evolution_diagram.py`）
- 分析：harness 与 framework/MCP/plugin/sandbox/CI 的关系；Agent 本质定义与循环证明

## 文件

| 文件 | 说明 |
|---|---|
| `layers.py` | 四层递进实验脚本（支持断点续跑：`python layers.py <总层数> <起始层>`） |
| `rubric.py` | 八项要点检查器（prompt→loop 共用的评分约束） |
| `common_ch2.py` | 公共模块（环境变量/日志/计时） |
| `README.md` | 本文件 |

## 运行（实验证据 → evidence/ch2/）

```sh
# 需 code/ch1-api/.env 中的 MOONSHOT_API_KEY
E:\Miniconda\envs\ML-base\python.exe layers.py 4      # 全四层
E:\Miniconda\envs\ML-base\python.exe layers.py 4 3    # 从第 3 层续跑
```

> 注意：单次 kimi-k3 调用约 100s（推理模型长输出），建议后台运行。
