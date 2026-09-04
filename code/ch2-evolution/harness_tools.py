# -*- coding: utf-8 -*-
"""
harness_tools.py —— 第 2 章实验的真实 harness（工具 + 脚本 + 测试）

【来源】本文件是"学习 Claude Code 的 Agent 模式"教学代码的改编：
  - 循环模式（模型输出 → 执行工具 → 结果回传 → 下一轮请求）改编自
    s01_agent_loop.py（`learn-claude-code/agents/`）；
  - 工具分发（TOOLS schema + TOOL_HANDLERS 路由 map）改编自
    s02_tool_use.py；
  - 改编点：① SDK 由 Anthropic 换成 OpenAI-compatible（实验模型
    mimo-v2.5 已验证支持 tool calling）；② 工具集换成"教程任务"专用
    （write_file / bash / run_tests）；③ 新增安全边界——模型只能写入
    SANDBOX 目录、bash 有危险命令黑名单（沿用 s01 思路）。

【什么是"真 harness"】任务书第 2 章：Harness 层= 加入脚本、测试、
JSON 校验、评分 rubrics——模型外部的运行时能力。本文件实现三件套：
  1. 工具（write_file/bash）：模型能写文件、能执行命令（让 agent 面对
     真实环境而不是空想）；
  2. 测试（run_tests → tests/test_tutorial.py）：模型写完教程后由
     独立测试脚本验证（JSON 结构/五字段/八项要点/引用格式），
     测试结论由代码判定并回传，模型无法自评；
  3. 安全边界：写文件限制在 SANDBOX 内、bash 危险命令黑名单。

【用法】在 layers.py 第 3/4 层导入：
  from harness_tools import ToolAgent
  agent = ToolAgent(client, model)
  final_text = agent.run(messages)     # 返回模型最终输出（含工具调用轨迹的日志）
"""
import os
import json
import subprocess
from pathlib import Path

# ---- 沙箱目录：模型唯一能写入的位置（改一行 SANDBOX 即可隔离所有产出）----
BASE_DIR = Path(__file__).parent
WORKSPACE_ROOT = BASE_DIR.parent.parent          # code/ch2-evolution -> 工作区根
SANDBOX = Path(os.environ.get("CH2_SANDBOX", WORKSPACE_ROOT / "evidence" / "ch2" / "sandbox"))
TEST_SCRIPT = BASE_DIR / "tests" / "test_tutorial.py"

# ---- 工具 1：bash（改编 s01 run_bash：黑名单 + 超时 + 输出截断）----
DANGEROUS = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/", "mkfs", "format "]


def run_bash(command: str) -> str:
    """执行 shell 命令（黑名单保护；模型可运行测试脚本/查看文件等）。"""
    if any(d in command for d in DANGEROUS):
        return "Error: Dangerous command blocked by policy"
    try:
        r = subprocess.run(command, shell=True, cwd=SANDBOX,
                           capture_output=True, text=True, timeout=120)
        out = (r.stdout + r.stderr).strip()
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"
    except (FileNotFoundError, OSError) as e:
        return f"Error: {e}"


# ---- 工具 2：write_file（安全边界：只允许写在 SANDBOX 内）----
def safe_path(path: str) -> Path:
    p = (SANDBOX / path).resolve()
    if not p.is_relative_to(SANDBOX):
        raise ValueError(f"Path escapes sandbox: {path}")
    return p


def run_write(path: str, content: str) -> str:
    """把内容写入沙箱内的文件（教程 JSON / 辅助脚本都从这里落盘）。"""
    try:
        fp = safe_path(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} chars to sandbox:{path}"
    except Exception as e:
        return f"Error: {e}"


# ---- 工具 3：run_tests（独立测试脚本，判定结论由代码给出）----
def run_tests(path: str = "tutorial.json") -> str:
    """对沙箱内教程文件运行测试脚本（tests/test_tutorial.py），返回逐项结果。"""
    try:
        fp = safe_path(path)
        if not fp.exists():
            return f"Error: {path} not found in sandbox"
        r = subprocess.run(
            [os.environ.get("PYTHON3", "E:\\Miniconda\\envs\\ML-base\\python.exe"),
             str(TEST_SCRIPT), str(fp)],
            capture_output=True, text=True, timeout=120, cwd=str(BASE_DIR.parent),
        )
        return (r.stdout + r.stderr).strip()[:20000] or "(no output)"
    except Exception as e:
        return f"Error: {e}"


# ---- 工具注册表（schema 格式：OpenAI-compatible，mimo-v2.5 已实测支持）----
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "把内容写入沙箱目录下的文件（教程 JSON 用这个落盘）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "沙箱内相对路径"},
                    "content": {"type": "string", "description": "文件完整内容"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": "对 sandbox/tutorial.json 运行测试脚本，返回逐项通过/失败结果。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "默认 tutorial.json"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "执行 shell 命令（工作目录=sandbox；危险命令被政策拦截）。",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    },
]

# ---- 分发表（改编 s02 TOOL_HANDLERS）----
HANDLERS = {
    "write_file": run_write,
    "run_tests": run_tests,
    "bash": lambda **kw: run_bash(kw["command"]),
}


class ToolAgent:
    """带工具循环的智能体（s01/s02 的 while 循环，OpenAI-compatible 版）。

    循环规则（沿用教学代码的核心模式）：
      1. 请求模型（带工具 schema）→ 响应可能含 tool_calls；
      2. 若无 tool_calls：模型已给出最终回答，循环结束；
      3. 若有：逐个执行工具 → 把 tool_result 以 {"role":"tool"} 回传 →
         继续下一轮请求（模型看到工具结果后决定继续还是停止）。
    """

    def __init__(self, client, model: str, log=print):
        self.client = client
        self.model = model
        self.log = log

    def run(self, messages: list, max_tool_turns: int = 12) -> str:
        """跑工具循环（轮数上限由调用方决定），把走过的每一步写进日志。

        max_tool_turns 的意义：控制"行动-验证-再修正"的周期数。
          - 第 3 层 harness 传 2（模型只能写文件 + 跑测试各一次，测试失败
            即记录失败——harness 能验证、不自动迭代）；
          - 第 4 层 loop 传 12（由外部程序在测试失败后注入反馈重启循环）。
        """
        tool_turns = 0
        for turn in range(1, 13):   # 软上限：12 个模型回合防死循环（s01 无上限，这里保守）
            resp = self.client.chat.completions.create(
                model=self.model, messages=messages,
                tools=TOOLS, max_tokens=8000,
            )
            m = resp.choices[0].message
            u = resp.usage
            if u:
                self.log(f"  [回合 usage] prompt={u.prompt_tokens} "
                         f"completion={u.completion_tokens}（每次工具循环的模型请求都真实计费）")
            calls = getattr(m, "tool_calls", None)
            # 日志：模型这一回合干了什么（有调用=还在行动；没有=给出最终答复）
            if calls:
                tool_turns += 1
                if tool_turns > max_tool_turns:
                    # harness 层配额用尽：强制结束，不再让模型"自我修改"
                    self.log(f"  [turn {turn}] 工具回合已达上限 {max_tool_turns}，强制结束"
                             f"（harness 验证面完成，不自动迭代）")
                    return m.content or ""
                for c in calls:
                    args = c.function.arguments or "{}"
                    self.log(f"  [turn {turn}] 模型调用工具 {c.function.name}({args[:120]})")
                # assistant 回合（含 tool_calls）追加进历史 → 这是 s01 的"append assistant turn"
                messages.append({
                    "role": "assistant",
                    "content": m.content,
                    "tool_calls": [
                        {"id": c.id, "type": "function",
                         "function": {"name": c.function.name,
                                      "arguments": c.function.arguments or "{}"}}
                        for c in calls
                    ],
                })
                # 逐个执行工具，结果以 tool 角色回传（s01 的"append results"）
                for c in calls:
                    handler = HANDLERS.get(c.function.name)
                    output = (handler(**json.loads(c.function.arguments))
                              if handler else f"Unknown tool: {c.function.name}")
                    self.log(f"    -> 工具结果：{output[:160]}")
                    messages.append({"role": "tool", "tool_call_id": c.id, "content": str(output)})
            else:
                # 模型不再调用工具 → 结束，返回最终答复
                self.log(f"  [turn {turn}] 模型停止工具调用，输出最终答复")
                return m.content or ""
        self.log("  [警告] 达到 12 回合软上限，强制结束")
        return messages[-1].get("content", "") or ""
