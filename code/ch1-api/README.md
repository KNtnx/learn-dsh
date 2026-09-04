# ch1-api —— 第 1 章：国内大模型 API 基础实验

## 实验清单（对应任务书第一章 7 项必做实验）

| # | 实验 | 文件 | 运行命令（ML-base 环境） |
|---|---|---|---|
| 1 | API key 与环境变量 | `.env`（自行填写） | — |
| 2 | curl 调用（≥2 provider） | `notes/curl_calls.md` | 见该文档 |
| 3 | Python 统一调用 | `unified_call.py` | `python unified_call.py kimi mimo` |
| 4 | 流式输出 | `stream_call.py` | `python stream_call.py kimi` |
| 5 | JSON 输出与校验 | `json_output.py` | `python json_output.py kimi` |
| 6 | 错误处理 | `error_cases.py` | `python error_cases.py kimi` |
| 7 | 模型对比（含图表） | `compare_models.py` | `python compare_models.py kimi mimo` |

## 使用步骤

1. 复制 `.env.example` 为 `.env`，填入至少两个平台的 key：
   - Kimi：`MOONSHOT_API_KEY`
   - 小米 MiMo：`MIMO_API_KEY`（平台 https://platform.xiaomimimo.com/#/console/api-keys）
   - 火山方舟：`ARK_API_KEY`（模型 ID 另填 `ARK_MODEL_ID`，可选）
   - 阿里云百炼：`DASHSCOPE_API_KEY`（可选）
2. 使用 Miniconda ML-base 环境运行（Python 3.11.15，依赖见 `requirements.txt`）：
   ```powershell
   E:\Miniconda\envs\ML-base\python.exe unified_call.py kimi mimo
   ```
3. 每个脚本会自动把真实输出写入 `evidence/ch1/`（UTF-8 日志），供报告引用。

## 补充脚本与文档

| 文件 | 说明 |
|---|---|
| `calc_cost.py` | 按官方单价 × 真实 usage 计算费用（证据 08_cost_summary.txt） |
| `check_env.py` | 环境检查（系统/版本/key 状态，脱敏显示） |
| `test_mimo_json.py` / `test_mimo_stream_usage.py` | MiMo 补充验证（JSON 行为/流式 usage） |
| `tutorial.md` | 第 1 章盲测教程（零基础同学一步步复现，含记录表与 FAQ） |
| `manual_screenshot_windows.ps1` / `user_screenshot.ps1` | 实验截图辅助（用户终端运行，自动/逐窗口截图） |

## 安全说明

- `.env` 已被 `.gitignore` 忽略，严禁提交；报告/日志中的 key 一律脱敏（`sk-***`）。
- 截图与日志中不得出现 API key、账户余额、内网 IP。
