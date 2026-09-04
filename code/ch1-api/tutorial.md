# 第 1 章盲测教程：从零开始调用国内大模型 API

> 本教程用于**盲测**：让一位没有 API 调用经验的同学，仅凭本文档一步步完成全部 7 个实验。
> 盲测者不需要任何前置知识，但需要：一台 Windows 电脑、能联网、有 Kimi 和/或小米 MiMo 的 API key。
> 盲测记录表见文末（第六节）。
> 关联材料：`AGENTS.md`（工作区约束）、`智能体实训安排_2026.pdf`（任务书第 1 章）、`notes/curl_calls.md`（curl 详解）、`notes/env-versions.md`（环境与费用）。

---

## 第一节 准备工作（约 20 分钟）

### 1.1 检查本机环境

打开 **PowerShell**（开始菜单搜索"PowerShell"），依次输入以下命令并记录输出：

```powershell
python --version      # 需要 3.10 及以上
node --version        # 需要 18 及以上（本实验只用 Python，Node 可选）
git --version         # 可选
curl --version        # 需要可用
jq --version          # 可选但推荐（1.8 小节安装；没装也不影响，可用 Python 替代）
```

> 如果 `python --version` 报"Python was not found"或版本低于 3.10，
> 直接进入 **1.2 安装 Miniconda**（推荐做法，一步到位）；
> 如果已经有 Python 3.10+，也要安装 Miniconda（见 1.2），因为本教程
> **统一使用 Miniconda 管理 Python 环境**（作者环境即为 Miniconda 的
> ML-base 环境，Python 3.11.15，这样盲测环境与作者环境一致，可复现性最好）。

### 1.2 安装 Miniconda

**什么是 Miniconda**：一个轻量的 Python 发行版 + 环境管理器。它自带 conda 命令，
可以创建相互隔离的 Python 虚拟环境（每个环境有独立的 Python 版本和依赖包），
避免"装一个包把系统搞坏"。

安装步骤：

1. **下载安装包**（任选一个源）：
   - 官网：https://docs.conda.io/en/latest/miniconda.html （Windows 版，约 80 MB）
   - 国内镜像（下载更快）：https://mirrors.tuna.tsinghua.edu.cn/anaconda/miniconda/
     选择 `Miniconda3-latest-Windows-x86_64.exe`
2. **双击安装**，一路 Next，注意两处：
   - 安装位置建议默认（如 `C:\Users\你的用户名\Miniconda3`）或自定义（如 `E:\Miniconda`）；
   - 在 "Advanced Installation Options" 页面，**勾选**：
     - `Add Miniconda3 to my PATH environment variable`（让终端能直接使用 conda 命令）
     - `Register Miniconda3 as my default Python 3.x`
3. 安装完成后**关闭并重新打开 PowerShell**（让 PATH 生效），验证：

```powershell
conda --version
```

预期输出形如 `conda 24.x.x`。若提示"conda 不是内部或外部命令"：
- 用开始菜单里的 **"Anaconda Prompt (miniconda3)"** 代替 PowerShell（它自带环境）；
- 或重新登录 Windows / 检查 PATH（见 FAQ）。

### 1.3 创建并激活 conda 虚拟环境

本教程为实验创建独立环境 `api-lab`（Python 3.11，与作者环境一致）：

```powershell
conda create -n api-lab python=3.11 -y
```

> `-n api-lab`：环境名；`python=3.11`：指定 Python 版本；`-y`：自动确认。
> 创建完成后每次使用前需要**激活**：

```powershell
conda activate api-lab
```

激活成功的标志：命令行开头出现 `(api-lab)`，例如：

```
(api-lab) PS C:\Users\你>
```

验证环境内的 Python 版本与位置：

```powershell
python --version     # 应显示 3.11.x
python -c "import sys; print(sys.prefix)"   # 应指向 ...\envs\api-lab
```

> **重要**：本教程后续所有命令（1.7 安装依赖、第三节所有实验）都必须在
> **已激活 api-lab 环境**的终端中执行。每开一个新终端窗口，先执行 `conda activate api-lab`。
> 作者本机的等价环境：`E:\Miniconda\envs\ML-base`（Python 3.11.15），
> 若你在作者机器上盲测，直接 `conda activate ML-base` 即可。

### 1.4 获取 API key（二选一或都做）

**Kimi（月之暗面）**：
1. 打开 https://platform.moonshot.cn （或 platform.kimi.com），注册/登录；
2. 进入控制台 → API Keys（密钥管理）→ 创建新的 API Key；
3. 复制生成的 key（形如 `sk-xxxxxxxx`），**只显示一次，注意保存**。

**小米 MiMo**：
1. 打开 https://platform.xiaomimimo.com ，注册/登录；
2. 控制台 → API Keys → 创建；
3. 复制 key（形如 `sk-xxxxxxxx`）。

> 安全规则（重要）：key 相当于密码。**任何情况下不要把 key 发给别人、不要写进代码文件、
> 不要出现在截图里**。本教程所有命令都用环境变量引用 key。

### 1.5 准备实验目录

```powershell
# 在任意位置创建实验目录（示例：E:\ch1-blind-test）
mkdir E:\ch1-blind-test
cd E:\ch1-blind-test
```

把工作区 `code\ch1-api` 目录下的**实验脚本**复制过来（common.py、unified_call.py、
stream_call.py、json_output.py、error_cases.py、compare_models.py、check_env.py）：
方式一：直接复制文件；方式二：在 PowerShell 中执行：

```powershell
Copy-Item E:\game\2026下半年暑假实训\code\ch1-api\*.py E:\ch1-blind-test\
```

### 1.6 配置 API key（环境变量）

在实验目录创建 `.env` 文件（用记事本），内容如下（**填入你自己的 key**）：

```
MOONSHOT_API_KEY=sk-你申请的Kimi密钥
MIMO_API_KEY=sk-你申请的MiMo密钥
```

保存后，在 PowerShell 中设置环境变量（每条命令执行一次，当前窗口有效）：

```powershell
$env:MOONSHOT_API_KEY = (Get-Content .env | Where-Object { $_ -like "MOONSHOT_API_KEY=*" }) -replace "MOONSHOT_API_KEY=", ""
$env:MIMO_API_KEY = (Get-Content .env | Where-Object { $_ -like "MIMO_API_KEY=*" }) -replace "MIMO_API_KEY=", ""
```

验证（**不会显示完整 key，只显示是否已设置**）：

```powershell
python check_env.py
```

预期看到：`[key] MOONSHOT_API_KEY 已配置（脱敏：sk-xxx***xxx）`。
如果显示"未配置"，检查 `.env` 文件内容与变量名是否拼错。

### 1.7 安装依赖（在 api-lab 环境中）

**先确认已激活环境**（命令行开头有 `(api-lab)`），然后执行：

```powershell
pip install openai matplotlib
```

> 若提示 pip 不是内部命令，改用 `python -m pip install openai matplotlib`。
> 安装完成后可用以下命令记录版本（任务书要求记录依赖版本）：
> 说明：本教程的 `.env` 由脚本内置加载器解析（无需 python-dotenv），
> HTTP 请求由 openai SDK 完成（无需 requests），所以只装这两个包。

```powershell
pip list | findstr /i "openai matplotlib"
```

### 1.8 安装 jq（JSON 查看工具，约 1 分钟）

**jq 是什么**：命令行 JSON 处理器，可以给 curl 返回的一长串 JSON 做
**美化缩进、提取指定字段、过滤**——相当于"JSON 界的 sed/grep"。
本仓库作者环境和任务书 8/20 的清单都包含它（任务书写"jq 或 Apifox"，装 jq 即可）。

打开 PowerShell，二选一执行（Windows 自带包管理器，任选其一）：

```powershell
scoop install jq      # 或
winget install jqlang.jq
```

安装后**关闭并重新打开 PowerShell**，验证：

```powershell
jq --version   # 显示 jq-1.8.x 即成功
```

> **如果装不上**：不影响本教程主体——所有 JSON 处理都可以用 Python 替代：
> `python -m json.tool`（只美化+校验）或教程第三节的脚本（用 `json.loads` 提取字段）。
> 报告环境表会如实记录安装情况。

---

## 第二节 实验 2：第一条 API 调用——curl（约 5 分钟）

> 本节命令不需要 Python 环境，但需要已配置环境变量（1.6 已完成）。

在 PowerShell 中执行（Kimi）：

```powershell
curl.exe -sS https://api.moonshot.cn/v1/chat/completions `
  -H "Content-Type: application/json" `
  -H "Authorization: Bearer $env:MOONSHOT_API_KEY" `
  -d '{"model":"kimi-k3","messages":[{"role":"user","content":"用一句话介绍 HTTP"}],"max_tokens":1000}'
```

**完成标志**：屏幕上出现一段 JSON，开头形如
`{"id":"chatcmpl-...","object":"chat.completion",...`，
其中 `choices[0].message.content` 有中文回答，`usage.total_tokens` 是数字。

**再看一眼**（可选）：把命令中的 `max_tokens` 改成 150 再执行一次，观察：
- `"finish_reason":"length"`（被截断）；
- `"content":""` 或很短（正文为空）；
- `usage` 里 `completion_tokens_details.reasoning_tokens` 接近 150。

> 解释：kimi-k3 是**推理模型**，会先"思考"再回答，思考内容也占 token 预算；
> `max_tokens` 太小会把正文挤没。这是推理模型的常见坑。

MiMo 版（把 URL、变量、model 换成 MiMo）：

```powershell
curl.exe -sS https://api.xiaomimimo.com/v1/chat/completions `
  -H "Content-Type: application/json" `
  -H "Authorization: Bearer $env:MIMO_API_KEY" `
  -d '{"model":"mimo-v2.5-pro","messages":[{"role":"user","content":"用一句话介绍 HTTP"}]}'
```

> 若报 `curl: (35) schannel: ... SEC_E_NO_CREDENTIALS`：说明当前环境无法访问证书凭据
> （DSH 沙箱限制），换普通终端或改用第三节的 Python 方式即可。

### 2.1 用 jq 查看响应（推荐，装了 1.8 的看这里）

**思路**：curl 输出 JSON → 用管道 `|` 交给 jq → jq 帮你格式化或只挑出你要的字段。

**用法 1：纯格式化**（把上一条 curl 命令末尾加上 `| jq` 即可，整行执行）：

```powershell
curl.exe -sS https://api.moonshot.cn/v1/chat/completions `
  -H "Content-Type: application/json" `
  -H "Authorization: Bearer $env:MOONSHOT_API_KEY" `
  -d '{"model":"kimi-k3","messages":[{"role":"user","content":"用一句话介绍 HTTP"}],"max_tokens":1000}' | jq
```

效果：JSON 带缩进和颜色分行显示，比一行长字符串好读得多。

**用法 2：只提取回答内容**（`choices[0].message.content` 就是模型回答）：

```powershell
# 上面的 curl 命令换成：…… | jq -r '.choices[0].message.content'
# -r 表示输出纯文本，不带 JSON 引号；去掉 -r 则保留 JSON 字符串形式
```

**用法 3：提取元数据**（请求 ID、token 用量——第 4 节算费用要用）：

```powershell
# …… | jq '{id: .id, finish_reason: .choices[0].finish_reason, usage: .usage}'
```

> **真实输出示例**（作者仓库里保存的真实响应文件 `evidence/ch1/02_curl_kimi_full.txt`）：
>
> ```text
> $ type 02_curl_kimi_full.txt | jq '{id: .id, finish_reason: .choices[0].finish_reason, usage: .usage}'
> {
>   "id": "chatcmpl-6a8457cbd5e7d7bf59c16745",
>   "finish_reason": "stop",
>   "usage": {
>     "prompt_tokens": 100,
>     "completion_tokens": 393,
>     "total_tokens": 493,
>     "cached_tokens": 100,
>     "completion_tokens_details": { "reasoning_tokens": 320 },
>     "prompt_tokens_details": { "cached_tokens": 100 }
>   }
> }
> ```
>
> 可以看到：模型实际消费 493 token（其中 320 是"思考"token——对应上面
> `max_tokens` 太小会挤掉正文的现象）。这就是第 7 节"模型对比"里
> 费用和速度数据的来源。

**注意**：
- `jq empty` 可以只做"校验 JSON 是否合法"（合法输出为空、退出码 0；非法报错退出码 4）。
- 如果没装 jq，等价替代：`python -m json.tool`（只美化+校验）或第 3 节的 Python 脚本（用 `json.loads` 提取字段）。

---

## 第三节 实验 3~7：Python 脚本（约 15 分钟）

> **先确认终端处于激活状态**：命令行开头应有 `(api-lab)`；
> 没有就先执行 `conda activate api-lab`。
> 在实验目录（含 .py 脚本）的 PowerShell 中依次执行，每步看"完成标志"：

### 实验 3 统一调用（一个脚本切换多个平台）

```powershell
python unified_call.py kimi mimo
```

**完成标志**：输出两个 provider 的 `[响应内容]` 与 `[usage  ] prompt_tokens=...`，
最后有"两模型对比摘要"。

> 若报 `环境变量 XXX 未设置`：回到 1.4 检查环境变量；
> 若报 `401`：key 填错或已失效。

### 实验 4 流式输出

```powershell
python stream_call.py kimi
```

**完成标志**：先出现大量 `delta.content=None` 的 chunk（模型思考中），
然后出现 `delta.content='流'`、`delta.content='式'` 这样的**逐字**输出，
最后有 `[流式] 首字节延迟（TTFT）=...s` 与普通调用对照。

### 实验 5 JSON 输出

```powershell
python json_output.py kimi
```

**完成标志**：输出一段 JSON（含 title/tasks/deadline/risks 四个字段），
并显示 `[json.loads] 解析成功` 与 `[结构校验] 通过`。

### 实验 6 错误处理（故意触发错误）

```powershell
python error_cases.py kimi
```

**完成标志**：出现 4 个错误案例，分别对应：
`401 AuthenticationError`（错误 key）、`404 NotFoundError`（错误模型名）、
`404`（错误 base_url）、`400 BadRequestError`（缺 messages）。

> 若某个案例显示"竟然成功了"，说明你的 key/网络环境与该案例预期不同，记录即可，不算失败。

### 实验 7 模型对比（含图表）

```powershell
python compare_models.py kimi mimo
```

**完成标志**：输出对比摘要（总耗时/TTFT/响应字数/JSON 可解析），
并在 `docs\figures\`（或脚本同级的上级 docs 目录）生成 `ch1_model_compare.png` 图表。

### 费用记录（可选加分）

```powershell
python calc_cost.py
```

**完成标志**：输出按官方单价 × 真实 usage 计算的费用汇总表与合计金额（应在 1 元以内量级）。

---

## 第四节 常见问题 FAQ

| 现象 | 原因 | 处理 |
|---|---|---|
| conda 不是内部或外部命令 | 安装时未勾选加入 PATH，或终端未重启 | 用开始菜单"Anaconda Prompt (miniconda3)"；或重开终端；或 `conda init powershell` 后重开 |
| conda activate 报错 | PowerShell 未初始化 conda | 先执行 `conda init powershell`，重开终端再 `conda activate api-lab` |
| python --version 不是 3.11 | 激活失败或用了系统 Python | 确认 `(api-lab)` 提示符；`python -c "import sys; print(sys.prefix)"` 应指向 envs\api-lab |
| pip 装到了全局（非环境内） | 未激活环境 | 激活后重装：`conda activate api-lab` 再 `pip install ...` |
| 401 Invalid Authentication | API key 错误/失效 | 重新复制 key，检查前后空格 |
| 404 Not found the model | 模型名拼写错误或平台无此模型 | 核对 `common.py` 中 model 字段 |
| 400 messages must not be empty | 请求体缺 messages | 检查代码中 messages 参数 |
| 429 Too Many Requests | 触发限流 | 等待 1 分钟重试；避免高并发 |
| 响应 content 为空、finish_reason=length | 推理 token 挤占 max_tokens | 调大 max_tokens（≥1000） |
| 终端中文乱码 | 控制台代码页不是 UTF-8 | 先执行 `chcp 65001` |
| MiMo 输出的 JSON 带 ```json 围栏 | 模型偶发格式不稳定 | 解析前剥离围栏，或重试一次 |
| curl 报 SEC_E_NO_CREDENTIALS | 沙箱环境无法访问证书 | 换普通终端或改用 Python 脚本 |



