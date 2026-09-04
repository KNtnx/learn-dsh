# 实验 2：curl 调用记录（POST /chat/completions）

> 运行日期：2026-08-18（以实际执行为准）
> 说明：所有命令中 API key 一律通过环境变量引用，**不出现明文**。
> 本机 JSON 工具：jq 1.8.2（scoop 安装；格式化/提取字段均可），亦可用
> `python -m json.tool` 只做美化+校验（任务书允许 jq 或等价工具）。
> **可复制性**：以下命令均可在 PowerShell 7 中直接复制运行（JSON 请求体使用单引号，
> 避免 `\"` 转义问题；cmd/bash 下需改为双引号+转义或 `--data @文件` 方式）。

## 2.1 curl 基本概念

- `-sS`：静默模式但保留错误输出（`-s` 静默，`-S` 出错时显示）。
- `-H`：请求头。两个关键 Header：
  - `Content-Type: application/json`：告诉服务器请求体是 JSON；
  - `Authorization: Bearer <API_KEY>`：Bearer token 鉴权（大模型 API 通用方式）。
- `-d`：请求体（Body），JSON 字符串；也可用 `--data @文件` 从文件读取。
- HTTP 状态码：`200` 成功；`400` 请求体错误；`401` 鉴权失败；`404` 路径不存在；`429` 限流。

## 2.2 Kimi（月之暗面）

```powershell
# 先设置环境变量（从 code/ch1-api/.env 读取，切勿写死在命令里）
# $env:MOONSHOT_API_KEY = "sk-..."   ← 在用户环境或 .env 中配置

# PowerShell 7 推荐写法：JSON 用单引号包裹，可直接复制运行
curl.exe -sS https://api.moonshot.cn/v1/chat/completions `
  -H "Content-Type: application/json" `
  -H "Authorization: Bearer $env:MOONSHOT_API_KEY" `
  -d '{"model":"kimi-k3","messages":[{"role":"user","content":"用一句话介绍 HTTP"}],"max_tokens":1000}'

# 等价写法：请求体写入文件后引用（避免引号转义问题，任何 shell 通用）
# Set-Content -Path req.json -Value '{"model":"kimi-k3","messages":[{"role":"user","content":"用一句话介绍 HTTP"}],"max_tokens":1000}' -Encoding utf8
# curl.exe -sS https://api.moonshot.cn/v1/chat/completions -H "Content-Type: application/json" -H "Authorization: Bearer $env:MOONSHOT_API_KEY" --data "@req.json"
```

> 注意：kimi-k3 是始终推理的模型，`max_tokens` 需预留推理 token 空间（实验中发现
> 150 上限会导致正文截断），建议 1000 以上。

## 2.3 Qwen（阿里云百炼，OpenAI 兼容模式）

```powershell
curl.exe -sS https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions `
  -H "Content-Type: application/json" `
  -H "Authorization: Bearer $env:DASHSCOPE_API_KEY" `
  -d '{"model":"qwen-plus","messages":[{"role":"user","content":"用一句话介绍 HTTP"}],"max_tokens":100}'
```

## 2.4 小米 MiMo（mimo.mi.com，OpenAI 兼容）

```powershell
# $env:MIMO_API_KEY = "sk-..."   ← 在 .env 或用户环境配置

curl.exe -sS https://api.xiaomimimo.com/v1/chat/completions `
  -H "Content-Type: application/json" `
  -H "Authorization: Bearer $env:MIMO_API_KEY" `
  -d '{"model":"mimo-v2.5-pro","messages":[{"role":"user","content":"用一句话介绍 HTTP"}]}'
```

> 注：mimo-v2.5-pro 默认开启思考模式，响应可能包含推理内容；思考模式下 temperature/top_p 参数无效。

## 2.5 火山方舟（Ark）

```powershell
curl.exe -sS https://ark.cn-beijing.volces.com/api/v3/chat/completions `
  -H "Content-Type: application/json" `
  -H "Authorization: Bearer $env:ARK_API_KEY" `
  -d '{"model":"<Model ID 或 Endpoint ID>","messages":[{"role":"user","content":"用一句话介绍 HTTP"}]}'
```

## 2.6 响应 JSON 字段解读（以 Kimi 为例）

```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "created": 1750000000,
  "model": "kimi-k3",
  "choices": [
    {
      "index": 0,
      "message": { "role": "assistant", "content": "..." },
      "finish_reason": "stop"
    }
  ],
  "usage": { "prompt_tokens": 25, "completion_tokens": 60, "total_tokens": 85 }
}
```

- `choices[0].message.content`：模型回答正文；
- `choices[0].finish_reason`：结束原因（`stop` 正常结束 / `length` 达到 max_tokens 截断）；
- `usage`：token 用量（计费依据：总费用 = prompt 单价 × prompt_tokens + 输出单价 × completion_tokens）；
- `created`：Unix 时间戳。

## 2.7 实际执行证据

实际运行输出见 `evidence/ch1/02_curl_kimi.txt`、`evidence/ch1/02_curl_qwen.txt`（运行实验时生成）。
