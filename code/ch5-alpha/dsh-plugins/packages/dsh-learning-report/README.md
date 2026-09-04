# dsh-learning-report

dsh 插件：**项目技术报告与复现方案**。用户要求分析、学习、调研某个项目，或要求写技术报告/复现方案时，一次收集结构化项目快照，并产出 `TECHNICAL_REPORT.md` 与 `REPRODUCTION.md`。

## 注册的工具

| 工具 | 说明 |
|------|------|
| `collect_project_context` | 一次性收集当前项目的结构化快照：依赖清单（自动识别 package.json/pyproject.toml/Cargo.toml/go.mod/requirements.txt）、README、AGENTS.md、源码文件清单、git 状态 |

## 分发的技能

| 技能 | 用途 |
|------|------|
| `project-learning-report` | 项目技术报告与复现方案工作流：收集上下文 → 创建输出目录 → 写 TECHNICAL_REPORT.md → 写 REPRODUCTION.md → 交付确认 |

## 依赖

运行时由宿主 dsh 提供（peerDependencies，optional）：

```json
"@deepseek-ai/cordis": "^4.0.1",
"@deepseek-ai/dsh-tools": "^0.1.1-rc.2",
"@deepseek-ai/dsh-skill-filesystem": "^0.1.1-rc.2"
```

## 安装

### 本地 tarball（当前推荐）

```bash
cd dsh-plugins/packages/dsh-learning-report
pnpm build          # 构建 lib/index.js
pnpm pack           # → dsh-learning-report-0.1.0.tgz

pnpm dsh plugin --profile web add ./dsh-plugins/packages/dsh-learning-report/dsh-learning-report-0.1.0.tgz
```

### 源码 checkout 直接开发

```bash
pnpm dsh plugin --profile web add ./dsh-plugins/packages/dsh-learning-report
```

### 发布到 npm 后

```bash
dsh plugin --profile web add dsh-learning-report
```

## 使用示例

```text
用户：分析一下当前项目，写一份技术报告和复现方案
模型：加载 project-learning-report 技能 → collect_project_context → 补读关键文件 →
     在 learning-<projectName>/ 下写 TECHNICAL_REPORT.md 与 REPRODUCTION.md
```

## 安全与注意事项

- 输出全部截断 + 限制条数 + `additionalProperties:false`，避免模型逐个 bash 探测；
- git 命令 5s 超时，失败返回 null 不抛错；
- 报告写入工作区 `learning-<projectName>/`，文件存在时追加或另命名，不覆盖；
- 不读 `.env`/密钥。

## 许可证与维护

MIT；维护者：本地个人插件（源自 deepseek-harness scratch-plugin）。
