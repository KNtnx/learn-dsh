import type { Context } from '@deepseek-ai/cordis'
import { defineTool } from '@deepseek-ai/dsh-tools'
import { execSync } from 'child_process'
import fs from 'fs/promises'
import path from 'path'

export const name = 'dev-snapshot-plugin'
export const inject = ['tools']

export function apply(ctx: Context) {
    ctx.tools.register(defineTool({
        name: 'dev_environment_snapshot',
        description: '探测当前开发环境的快照信息，包括目录、Git分支、Node/Python版本、包管理器和关键文件是否存在。',
        parameters: {},
        output: {
            schema: {
                type: 'object',
                properties: {
                    cwd: { type: 'string' },
                    gitBranch: { type: 'string' },
                    nodeVersion: { type: 'string' },
                    pythonVersion: { type: 'string' },
                    packageManager: { type: 'string' },
                    keyFiles: {
                        type: 'object',
                        properties: {
                            packageJson: { type: 'boolean' },
                            readme: { type: 'boolean' },
                            gitignore: { type: 'boolean' },
                        },
                        additionalProperties: false   // ⬅️ 关键修复
                    }
                },
                additionalProperties: false   // 顶层也加上（可选但推荐）
            },
            render: (_args, value) => [{
                type: 'text',
                text: JSON.stringify(value, null, 2)
            }],
        },
        async execute() {
            const cwd = process.cwd()
            
            let gitBranch = 'not a git repo'
            try {
                const stdout = execSync('git branch --show-current', { cwd, encoding: 'utf8' })
                gitBranch = stdout.trim() || 'detached HEAD'
            } catch {}

            const nodeVersion = process.version

            let pythonVersion = 'not found'
            try {
                const stdout = execSync('python3 --version', { encoding: 'utf8' })
                pythonVersion = stdout.trim()
            } catch {
                try {
                    const stdout = execSync('python --version', { encoding: 'utf8' })
                    pythonVersion = stdout.trim()
                } catch {}
            }

            let packageManager = 'none detected'
            try {
                await fs.access(path.join(cwd, 'pnpm-lock.yaml'))
                packageManager = 'pnpm'
            } catch {
                try {
                    await fs.access(path.join(cwd, 'package-lock.json'))
                    packageManager = 'npm'
                } catch {
                    try {
                        await fs.access(path.join(cwd, 'yarn.lock'))
                        packageManager = 'yarn'
                    } catch {}
                }
            }

            const keyFiles = {
                packageJson: false,
                readme: false,
                gitignore: false,
            }
            try {
                await fs.access(path.join(cwd, 'package.json'))
                keyFiles.packageJson = true
            } catch {}
            try {
                await fs.access(path.join(cwd, 'README.md'))
                keyFiles.readme = true
            } catch {}
            try {
                await fs.access(path.join(cwd, '.gitignore'))
                keyFiles.gitignore = true
            } catch {}

            return {
                cwd,
                gitBranch,
                nodeVersion,
                pythonVersion,
                packageManager,
                keyFiles,
            }
        },
    }))
}
