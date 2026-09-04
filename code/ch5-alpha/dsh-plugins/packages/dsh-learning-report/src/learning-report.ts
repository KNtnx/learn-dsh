/**
 * project-learning-report 插件入口：注册 collect_project_context 工具，
 * 并挂一个隔离的 skill-filesystem provider 分发配套技能（bundledSkillDir）。
 * 技能随插件包分发、不污染用户目录、编辑即时生效，不受 HMR 热重载影响。
 *
 * 设计目标（省 token）：
 * - 只新增 1 个工具：一次性抓取依赖/README/AGENTS.md/源码清单/git 状态的结构化快照；
 * - 输出全部截断 + 限制条数 + additionalProperties:false，避免模型逐个 bash 探测；
 * - 报告撰写复用内置 read/write，技能按需加载，不进每轮 system prompt。
 */

import type { Context } from '@deepseek-ai/cordis'
import { defineTool } from '@deepseek-ai/dsh-tools'
import Schema from '@deepseek-ai/schemastery'
import { apply as applyFilesystemProvider } from '@deepseek-ai/dsh-skill-filesystem'
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

export const name = 'project-learning-report'
export const inject = ['tools', 'skills']

/** 包内技能根目录（scratch-plugin/skills/learning-report/），随插件分发。 */
const SKILLS_ROOT = fileURLToPath(new URL('../skills/learning-report/', import.meta.url))

export interface Config {
	/** README / AGENTS.md 正文截断上限（字符）。 */
	docMaxChars?: number
	/** 源码文件清单条数上限。 */
	maxFiles?: number
	/** 文件树递归深度上限。 */
	treeDepth?: number
	/** git log 条数上限。 */
	maxGitLog?: number
	/** git status 行数上限。 */
	maxStatusLines?: number
	/** 依赖项条数上限。 */
	maxDeps?: number
}

export const Config: Schema<Config> = Schema.object({
	docMaxChars: Schema.number().default(8000),
	maxFiles: Schema.number().default(200),
	treeDepth: Schema.number().default(4),
	maxGitLog: Schema.number().default(20),
	maxStatusLines: Schema.number().default(50),
	maxDeps: Schema.number().default(50),
})

/** 递归列出源码文件（相对路径），排除构建/依赖/版本控制目录。 */
function listSourceFiles(root: string, maxFiles: number, maxDepth: number): { files: string[]; truncated: boolean } {
	const IGNORED_DIRS = new Set(['node_modules', '.git', '.next', 'target', 'dist', 'build', 'out', '__pycache__', '.venv', 'venv', 'vendor', '.dsh-build', 'lib'])
	const files: string[] = []
	let truncated = false
	const walk = (dir: string, depth: number): void => {
		if (depth > maxDepth || files.length >= maxFiles) {
			if (files.length >= maxFiles) truncated = true
			return
		}
		let entries: fs.Dirent[]
		try {
			entries = fs.readdirSync(dir, { withFileTypes: true })
		} catch {
			return
		}
		entries.sort((a, b) => a.name.localeCompare(b.name))
		for (const entry of entries) {
			if (files.length >= maxFiles) {
				truncated = true
				return
			}
			if (entry.name.startsWith('.') && entry.name !== '.gitignore') continue
			const full = path.join(dir, entry.name)
			if (entry.isDirectory()) {
				if (IGNORED_DIRS.has(entry.name)) continue
				walk(full, depth + 1)
			} else {
				files.push(path.relative(root, full))
			}
		}
	}
	walk(root, 0)
	return { files, truncated }
}

/** 读取文件全文，截断到上限；文件不存在返回空串。 */
function readTruncated(file: string, maxChars: number): string {
	try {
		const content = fs.readFileSync(file, 'utf8')
		return content.length > maxChars ? `${content.slice(0, maxChars)}\n…(已截断)` : content
	} catch {
		return ''
	}
}

/** 安全执行 git 命令，失败返回 null。 */
function git(cwd: string, args: string[]): string | null {
	try {
		return execFileSync('git', args, { cwd, encoding: 'utf8', timeout: 5000, stdio: ['ignore', 'pipe', 'pipe'] }).trim()
	} catch {
		return null
	}
}

/** 解析 package.json 依赖，返回 ["name@version", ...] 并截断。 */
function parsePackageJson(cwd: string, maxDeps: number): Record<string, unknown> | null {
	const file = path.join(cwd, 'package.json')
	if (!fs.existsSync(file)) return null
	try {
		const raw = JSON.parse(fs.readFileSync(file, 'utf8')) as Record<string, unknown>
		const collect = (section: string): string[] => {
			const deps = raw[section]
			if (typeof deps !== 'object' || deps === null) return []
			return Object.entries(deps as Record<string, unknown>)
				.slice(0, maxDeps)
				.map(([name, version]) => `${name}@${String(version)}`)
		}
		const scripts = raw['scripts']
		const scriptsSummary = typeof scripts === 'object' && scripts !== null
			? Object.fromEntries(Object.entries(scripts as Record<string, string>).slice(0, 10))
			: {}
		return {
			type: 'npm',
			name: typeof raw['name'] === 'string' ? raw['name'] : '',
			version: typeof raw['version'] === 'string' ? raw['version'] : '',
			dependencies: collect('dependencies'),
			devDependencies: collect('devDependencies'),
			scripts: scriptsSummary,
		}
	} catch {
		return null
	}
}

/** 解析 requirements.txt。 */
function parseRequirements(cwd: string, maxDeps: number): Record<string, unknown> | null {
	const file = path.join(cwd, 'requirements.txt')
	if (!fs.existsSync(file)) return null
	try {
		const lines = fs.readFileSync(file, 'utf8')
			.split('\n')
			.map(line => line.trim())
			.filter(line => line.length > 0 && !line.startsWith('#'))
			.slice(0, maxDeps)
		return { type: 'python', dependencies: lines }
	} catch {
		return null
	}
}

/** 解析 Cargo.toml 的 [dependencies] 段（简化）。 */
function parseCargoToml(cwd: string, maxDeps: number): Record<string, unknown> | null {
	const file = path.join(cwd, 'Cargo.toml')
	if (!fs.existsSync(file)) return null
	try {
		const content = fs.readFileSync(file, 'utf8')
		const name = /^name\s*=\s*"([^"]+)"/m.exec(content)?.[1] ?? ''
		const version = /^version\s*=\s*"([^"]+)"/m.exec(content)?.[1] ?? ''
		const deps: string[] = []
		const inDeps = content.split('\n').findIndex(line => /^\[dependencies\]/.test(line))
		if (inDeps >= 0) {
			for (const line of content.split('\n').slice(inDeps + 1)) {
				if (/^\[/.test(line)) break
				const m = /^\s*([a-zA-Z0-9_-]+)\s*=\s*(.+)/.exec(line)
				if (m) deps.push(`${m[1]}@${m[2]!.trim()}`)
				if (deps.length >= maxDeps) break
			}
		}
		return { type: 'rust', name, version, dependencies: deps }
	} catch {
		return null
	}
}

/** 解析 go.mod 的 require 段（简化）。 */
function parseGoMod(cwd: string, maxDeps: number): Record<string, unknown> | null {
	const file = path.join(cwd, 'go.mod')
	if (!fs.existsSync(file)) return null
	try {
		const content = fs.readFileSync(file, 'utf8')
		const moduleName = /^module\s+(.+)$/m.exec(content)?.[1]?.trim() ?? ''
		const deps: string[] = []
		const inRequire = content.split('\n').findIndex(line => /^require\s*\(/.test(line))
		if (inRequire >= 0) {
			for (const line of content.split('\n').slice(inRequire + 1)) {
				if (/^\)/.test(line)) break
				const trimmed = line.trim()
				if (!trimmed) continue
				const parts = trimmed.split(/\s+/)
				if (parts[0]) deps.push(parts.slice(0, 2).join('@'))
				if (deps.length >= maxDeps) break
			}
		}
		return { type: 'go', name: moduleName, dependencies: deps }
	} catch {
		return null
	}
}

/** 解析 pyproject.toml 的依赖（简化）。 */
function parsePyProject(cwd: string, maxDeps: number): Record<string, unknown> | null {
	const file = path.join(cwd, 'pyproject.toml')
	if (!fs.existsSync(file)) return null
	try {
		const content = fs.readFileSync(file, 'utf8')
		const name = /^name\s*=\s*"([^"]+)"/m.exec(content)?.[1] ?? ''
		const version = /^version\s*=\s*"([^"]+)"/m.exec(content)?.[1] ?? ''
		const deps: string[] = []
		const inDeps = content.split('\n').findIndex(line => /^dependencies\s*=/.test(line))
		if (inDeps >= 0) {
			for (const line of content.split('\n').slice(inDeps + 1)) {
				const m = /^\s*"([^"]+)".*/.exec(line)
				if (m) {
					deps.push(m[1]!)
					if (deps.length >= maxDeps) break
				}
				if (/^\s*\]/.test(line) && deps.length > 0) break
			}
		}
		return { type: 'python', name, version, dependencies: deps }
	} catch {
		return null
	}
}

export function apply(ctx: Context, config: Config = {}): void {
	console.log('[project-learning-report] ✅ 插件已加载！')

	const docMaxChars = config.docMaxChars ?? 8000
	const maxFiles = config.maxFiles ?? 200
	const treeDepth = config.treeDepth ?? 4
	const maxGitLog = config.maxGitLog ?? 20
	const maxStatusLines = config.maxStatusLines ?? 50
	const maxDeps = config.maxDeps ?? 50

	// ---------- 工具：collect_project_context ----------
	ctx.tools.register(defineTool({
		name: 'collect_project_context',
		description: '一次性收集当前项目的结构化快照：依赖清单（自动识别 package.json/pyproject.toml/Cargo.toml/go.mod/requirements.txt）、README、AGENTS.md、源码文件清单、git 状态。写技术报告前先调用它。',
		parameters: {},
		output: {
			schema: {
				type: 'object',
				additionalProperties: false,
				properties: {
					cwd: { type: 'string', required: true },
					projectName: { type: 'string', required: true },
					hasGit: { type: 'boolean', required: true },
					git: {
						type: 'object',
						required: true,
						additionalProperties: false,
						properties: {
							branch: { type: 'string', required: true },
							status: { type: 'array', required: true, items: { type: 'string' } },
							recentLog: { type: 'array', required: true, items: { type: 'string' } },
							truncated: { type: 'boolean', required: true },
						},
					},
					manifest: {
						type: 'object',
						required: true,
						additionalProperties: false,
						properties: {
							type: { type: 'string', required: true },
							name: { type: 'string', required: true },
							version: { type: 'string', required: true },
							dependencies: { type: 'array', required: true, items: { type: 'string' } },
							devDependencies: { type: 'array', required: true, items: { type: 'string' } },
							scripts: {
								type: 'object',
								required: true,
								additionalProperties: true,
							},
						},
					},
					readme: { type: 'string', required: true },
					agentsDoc: { type: 'string', required: true },
					files: { type: 'array', required: true, items: { type: 'string' } },
					truncated: {
						type: 'object',
						required: true,
						additionalProperties: false,
						properties: {
							readme: { type: 'boolean', required: true },
							agentsDoc: { type: 'boolean', required: true },
							files: { type: 'boolean', required: true },
							gitStatus: { type: 'boolean', required: true },
							gitLog: { type: 'boolean', required: true },
						},
					},
				},
			},
			render: (_args, value) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
		},
		async execute(_args, exec) {
			exec.signal.throwIfAborted()
			const cwd = exec.agent?.session.header.cwd ?? process.cwd()
			const projectName = path.basename(cwd)

			// git 状态
			const hasGit = git(cwd, ['rev-parse', '--is-inside-work-tree']) === 'true'
			let branch = ''
			let statusLines: string[] = []
			let logLines: string[] = []
			let gitStatusTruncated = false
			let gitLogTruncated = false
			if (hasGit) {
				branch = git(cwd, ['branch', '--show-current']) ?? ''
				const status = git(cwd, ['status', '--short']) ?? ''
				const statusAll = status.split('\n').filter(line => line.length > 0)
				gitStatusTruncated = statusAll.length > maxStatusLines
				statusLines = statusAll.slice(0, maxStatusLines)
				const log = git(cwd, ['log', '--oneline', `-n ${maxGitLog}`]) ?? ''
				const logAll = log.split('\n').filter(line => line.length > 0)
				gitLogTruncated = logAll.length >= maxGitLog
				logLines = logAll.slice(0, maxGitLog)
			}

			// 清单（按优先级取第一个命中的）
			const manifest = parsePackageJson(cwd, maxDeps)
				?? parsePyProject(cwd, maxDeps)
				?? parseCargoToml(cwd, maxDeps)
				?? parseGoMod(cwd, maxDeps)
				?? parseRequirements(cwd, maxDeps)
				?? { type: 'unknown', name: '', version: '', dependencies: [], devDependencies: [], scripts: {} }

			// README / AGENTS.md（README.md 优先，其次 README.zh.md）
			const readmePath = [path.join(cwd, 'README.md'), path.join(cwd, 'README.zh.md')].find(p => fs.existsSync(p))
			const readme = readmePath !== undefined ? readTruncated(readmePath, docMaxChars) : ''
			const agentsPath = path.join(cwd, 'AGENTS.md')
			const agentsDoc = fs.existsSync(agentsPath) ? readTruncated(agentsPath, docMaxChars) : ''

			const { files, truncated: filesTruncated } = listSourceFiles(cwd, maxFiles, treeDepth)

			return {
				cwd,
				projectName,
				hasGit,
				git: {
					branch,
					status: statusLines,
					recentLog: logLines,
					truncated: gitStatusTruncated || gitLogTruncated,
				},
				manifest: {
					...manifest,
					devDependencies: Array.isArray(manifest.devDependencies) ? manifest.devDependencies : [],
					scripts: typeof manifest.scripts === 'object' && manifest.scripts !== null ? manifest.scripts : {},
				},
				readme,
				agentsDoc,
				files,
				truncated: {
					readme: readme.length >= docMaxChars,
					agentsDoc: agentsDoc.length >= docMaxChars,
					files: filesTruncated,
					gitStatus: gitStatusTruncated,
					gitLog: gitLogTruncated,
				},
			}
		},
	}))

	// ---------- 技能：隔离 filesystem provider（随包分发） ----------
	// 只扫描本包 skills/learning-report/ 树，不碰项目/用户默认根；watch 关闭，避免 HMR 竞态。
	applyFilesystemProvider(ctx, {
		providerName: 'project-learning-report',
		includeDefaultRoots: false,
		watch: false,
		bundledSkillDir: SKILLS_ROOT,
	})
}
