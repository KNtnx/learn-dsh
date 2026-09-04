import type { Context } from '@deepseek-ai/cordis'
import { defineTool } from '@deepseek-ai/dsh-tools'

export const name = 'my-first-plugin'
export const inject = ['tools']   // 依赖 tools 服务

export function apply(ctx: Context) {
    // 实验1：打印日志
    console.log('[my-plugin] ✅ 插件已加载！')

    // 实验2：注册 greet 工具
    ctx.tools.register(defineTool({
        name: 'greet',
        description: 'Greet someone by name.',
        parameters: {
            name: {
                type: 'string',
                required: true,
                description: 'The name to greet'
            }
        },
        output: {
            schema: { type: 'string' },
            render: (_args, value) => [{ type: 'text', text: value }]
        },
        async execute(args) {
            return `Hello, ${args.name}!`
        }
    }))
}
