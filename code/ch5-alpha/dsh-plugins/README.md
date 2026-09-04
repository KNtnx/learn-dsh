# dsh-plugins — dsh 个人插件 monorepo

一组可被 **dsh**（DeepSeek Harness，npm 安装版 `@deepseek-ai/dsh`）加载的 bundle 插件集合。每个插件是一个独立 npm 包，声明 `dsh.bundle` manifest，通过 `dsh plugin --profile <name> add <pkg>` 安装。

## 插件清单

| 包 | 注册的工具 | 技能 | 用途 |
|----|-----------|------|------|
| [`dsh-latex-helpers`](./packages/dsh-latex-helpers/) | `generate_latex_report` / `compile_latex` / `cleanup_latex_aux` / `write_experiment_report` | — | LaTeX 实验报告：生成脚手架 → 编译 → 清理 |
| [`dsh-code-verifier`](./packages/dsh-code-verifier/) | `probe_toolchain` / `verify_code` | `code-verifier-workflow` | 代码编写与验证工作流 |
| [`dsh-learning-report`](./packages/dsh-learning-report/) | `collect_project_context` | `project-learning-report` | 项目技术报告与复现方案 |
| [`dsh-pdf-summarizer`](./packages/dsh-pdf-summarizer/) | `extract_pdf_text` / `render_pdf_pages` / `generate_latex_document` | `pdf-summarizer` | PDF 阅读 → LaTeX 文档 → 编译 |
| [`dsh-greet`](./packages/dsh-greet/) | `greet` | — | hello-world 问候工具 |
| [`dsh-dev-snapshot`](./packages/dsh-dev-snapshot/) | `dev_environment_snapshot` | — | 开发环境快照 |

## 目录结构

```
dsh-plugins/
├── pnpm-workspace.yaml
├── package.json
└── packages/<pkg>/
    ├── package.json        # dsh.bundle.patch manifest + peerDependencies
    ├── cordis.patch.yml    # - insert: [{id, name: <pkg>}]
    ├── README.md
    ├── src/*.ts            # 插件源码
    ├── skills/...          # 仅带技能的包
    └── lib/index.js        # 构建产物（esbuild，@deepseek-ai/* external）
```

## 依赖解析原理

插件源码 `import { defineTool } from '@deepseek-ai/dsh-tools'` 等运行时依赖**不随包发布**，而是声明为 peerDependencies（optional）。dsh 安装的依赖闭包（dsh-base → dsh-tools/dsh-skill-filesystem，dsh-web-app → schemastery，dsh → cordis）通过 `$DSH_HOME/profiles/node_modules` 父级查找为插件提供这些包——这是官方 bundle 机制的设计（"组合包可放心依赖 @deepseek-ai/dsh-base 存在且与安装保持一致"）。

## 构建与打包

需要本机已安装 esbuild（或从 dsh 仓库的 `node_modules/.bin/esbuild` 调用）：

```bash
# 构建单个包
cd packages/dsh-latex-helpers
pnpm build          # esbuild --bundle --platform=node --format=esm --external:@deepseek-ai/* → lib/index.js
pnpm pack           # → dsh-latex-helpers-0.1.0.tgz

# 构建全部（在 monorepo 根）
cd dsh-plugins
pnpm -r run build
```

## 安装到 dsh

```bash
# 在 dsh 仓库根目录（或有 dsh CLI 的环境）
# 方式一：tarball
pnpm dsh plugin --profile web add ./dsh-plugins/packages/dsh-latex-helpers/dsh-latex-helpers-0.1.0.tgz

# 方式二：源码目录（开发模式）
pnpm dsh plugin --profile web add ./dsh-plugins/packages/dsh-latex-helpers

# 方式三：npm registry（需已发布）
dsh plugin --profile web add dsh-latex-helpers

# 验证层
pnpm dsh --profile web --dump-config
pnpm dsh --profile web
```

## 发布到 npm

```bash
cd packages/dsh-latex-helpers
pnpm build
pnpm publish --access public    # prepublishOnly 会自动先 build
```

> 提示：当前 `@deepseek-ai/dsh` 已发布（如 `0.1.1-rc.2`），依赖闭包完整，插件可作为公开 npm 包安装。若只想私有使用，本地 tarball 即可，无需发布。

## 从 scratch-plugin 迁移说明

本 monorepo 是 `scratch-plugin/` 的打包版整理：
- 每个插件独立成包（`dsh-<name>`），技能随包分发（`skills/`）；
- `cordis.patch.yml` 的 `name` 用**包名**而非绝对路径；
- 旧 `~/.dsh-agent-lab/profiles/web/cordis.patch.yml` 中的绝对路径行与新 bundle 行可共存，迁移完成后再移除旧行。

## 许可证

MIT（各包独立声明）。
