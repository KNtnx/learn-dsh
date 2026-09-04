// ============================================================
// latex-helpers.ts —— 个人 Alpha 插件：LaTeX 实验报告助手
//
// 一句话价值：用户说"用 latex 写实验报告"时，模型自动调用本插件，
// 按统一规格完成 生成 → 编译 → 清理中间文件，无需反复交代
// 排版/字号/编译命令/文件清理（省 token、保证格式一致）。
//
// 规格（用户给定，内嵌模板）：
//   - 编译：latexmk -xelatex -halt-on-error main.tex
//   - 行距 1.5 倍；正文首行缩进 2 字符
//   - 中文黑体/宋体（ctex \heiti/\songti）+ 英文数字 Times New Roman
//   - 题目黑体小二；作者宋体小四；一级标题黑体四号；二级及以下
//     黑体或宋体加粗小四；正文/摘要宋体小四；图表标题/注释、
//     参考文献宋体小五
//   - 中间文件默认删除（keep=true 则保留）
//
// 安全约束（对齐任务书第 5 条）：
//   - 写入仅限参数指定的 outputDir；
//   - 编译用 execFile（参数数组，不经 shell）且命令固定为
//     latexmk -xelatex -halt-on-error <file>（白名单）；
//   - 清理仅限指定目录下 9 类 LaTeX 中间文件扩展名；
//   - 不读 .env/密钥；返回内容不含任何凭据。
// ============================================================

import type { Context } from '@deepseek-ai/cordis'
import { defineTool } from '@deepseek-ai/dsh-tools'
import { execFileSync } from 'node:child_process'
import { mkdirSync, readdirSync, writeFileSync, rmSync, existsSync } from 'node:fs'
import path from 'node:path'

export const name = 'latex-helpers-plugin'
export const inject = ['tools']

// ---- 中间文件扩展名（清理白名单）----
const AUX_EXTS = [
  '.aux', '.log', '.out', '.toc', '.fls', '.fdb_latexmk',
  '.synctex.gz', '.xdv', '.bbl', '.blg',
]

// ---- 编译命令模板（白名单：仅此一条，参数数组无 shell）----
function compile(dir: string, file: string) {
  return execFileSync('latexmk', ['-xelatex', '-halt-on-error', file], {
    cwd: dir, encoding: 'utf8', timeout: 600_000, maxBuffer: 8 * 1024 * 1024,
  })
}

// ---- 清理中间文件：仅匹配扩展名白名单，返回删除清单 ----
function cleanupAux(dir: string, keep: boolean): string[] {
  if (keep || !existsSync(dir)) return []
  const removed: string[] = []
  for (const f of readdirSync(dir)) {
    if (AUX_EXTS.some((ext) => f.endsWith(ext))) {
      rmSync(path.join(dir, f), { force: true })
      removed.push(f)
    }
  }
  return removed
}

// ---- 模板：按用户规格生成 main.tex（黑体/宋体 + Times + 1.5 行距 + 缩进）----
function buildMainTex(title: string, author: string, studentId: string,
                      group: string, date: string,
                      sections: string[]): string {
  const inputs = sections.map((_, i) => `\\input{ch${i + 1}.tex}`).join('\n')
  return `% 由 latex-helpers 插件生成（个人 Alpha·实验报告助手）
% 排版规格：1.5 倍行距 / 首行缩进 2 字符 / 中文黑体·宋体 / 英文数字 Times New Roman
%      题目黑体小二 / 作者宋体小四 / 一级标题黑体四号 / 二级及以下黑体或宋体加粗小四
%      正文·摘要宋体小四 / 图表标题·注释·参考文献宋体小五
% 编译命令：latexmk -xelatex -halt-on-error main.tex
\\documentclass[12pt,a4paper]{ctexart}

\\usepackage[top=2.54cm,bottom=2.54cm,left=3.17cm,right=3.17cm]{geometry}
\\usepackage{setspace}\\setstretch{1.5}   % 1.5 倍行距
\\setlength{\\parindent}{2em}            % 首行缩进 2 字符
\\setmainfont{Times New Roman}           % 英文与数字

\\usepackage{graphicx}\\usepackage{float}
\\usepackage{booktabs}\\usepackage{array}\\usepackage{multirow}
\\usepackage{caption}\\usepackage{enumitem}
\\usepackage[colorlinks,linkcolor=black,citecolor=black,urlcolor=black]{hyperref}

\\captionsetup{labelformat=zh,font=scriptsize}   % 图表标题：小五（\\zihao{-5} 近似）

% 标题层级样式（对应规格表）
\\ctexset{
  section     = { format = {\\raggedright\\heiti\\zihao{4}} },     % 一级：黑体 四号
  subsection  = { format = {\\raggedright\\heiti\\zihao{-4}} },    % 二级：黑体 小四
  subsubsection = { format = {\\raggedright\\songti\\bfseries\\zihao{-4}} }, % 三级：宋体加粗 小四
}

\\newcommand{\\titledesk}{\\heiti\\zihao{2}}       % 论文题目：黑体 小二
\\newcommand{\\authordesk}{\\songti\\zihao{-4}}    % 作者信息：宋体 小四

\\begin{document}
\\begin{titlepage}
\\begin{center}
    \\vspace*{4cm}
    {\\titledesk ${escape(title)}}\\\\[14pt]
    {\\authordesk ${escape(author)}（${escape(studentId)}）}\\\\[6pt]
    {\\authordesk ${escape(group)}：${escape(date)}}
\\end{center}
\\end{titlepage}
\\tableofcontents
\\clearpage

${inputs}

\\end{document}
`
}

// ---- 章节模板 ----
function buildChapterTex(idx: number, title: string): string {
  return `% ch${idx}.tex（由 latex-helpers 插件生成）
\\clearpage
\\section{${escape(title)}}
`
}

// 转义用户文本中的 LaTeX 特殊字符（防模板注入）
function escape(s: string): string {
  return s.replace(/[\\\\{}%&$#_^~]/g, (c) => '\\' + c)
}

export function apply(ctx: Context) {
  // ---------- 工具 1：生成报告脚手架（规格模板） ----------
  ctx.tools.register(defineTool({
    name: 'generate_latex_report',
    description:
      '按统一规格（1.5 倍行距/首行缩进/黑体宋体+Times/字号表）生成 LaTeX 实验' +
      '报告脚手架：main.tex + 各章 chN.tex，写入参数 outputDir（默认 report/）。' +
      '用户说"用 latex 写实验报告"时应调用本插件。',
    parameters: {
      title: { type: 'string', required: true, description: '报告题目' },
      author: { type: 'string', description: '作者姓名' },
      studentId: { type: 'string', description: '学号' },
      group: { type: 'string', description: '群名/课程名' },
      date: { type: 'string', description: '提交日期，如 YYYY-MM-DD' },
      sections: { type: 'array', items: { type: 'string' }, description: '章节标题列表' },
      outputDir: { type: 'string', description: '输出目录，默认 report' },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          message: { type: 'string' },
          files: { type: 'array', items: { type: 'string' } },
        },
      },
      render: (_args, value) => [{ type: 'text', text: value.message }],
    },
    async execute(args) {
      const dir = path.resolve(args.outputDir || 'report')
      mkdirSync(dir, { recursive: true })
      const sections = args.sections?.length ? args.sections : ['第一章：背景', '第二章：实验', '结论']
      writeFileSync(path.join(dir, 'main.tex'),
        buildMainTex(args.title, args.author || '', args.studentId || '',
                    args.group || '', args.date || '', sections), 'utf8')
      const files = ['main.tex']
      sections.forEach((s, i) => {
        writeFileSync(path.join(dir, `ch${i + 1}.tex`), buildChapterTex(i + 1, s), 'utf8')
        files.push(`ch${i + 1}.tex`)
      })
      return {
        message: `已在 ${dir} 生成 ${files.length} 个文件：${files.join('、')}；`
          + '排版规格已内嵌（1.5 倍行距/首行缩进 2 字符/黑体宋体+Times/字号表）。'
          + '编译：latexmk -xelatex -halt-on-error main.tex（可调用 compile_latex）。',
        files,
      }
    },
  }))

  // ---------- 工具 2：编译（命令白名单） ----------
  ctx.tools.register(defineTool({
    name: 'compile_latex',
    description:
      '编译 LaTeX 报告：执行固定白名单命令 latexmk -xelatex -halt-on-error ' +
      '<file>（不经 shell），返回日志关键行；默认顺带清理中间文件，' +
      'keepAux=true 时保留。',
    parameters: {
      dir: { type: 'string', description: '报告目录，默认 .' },
      file: { type: 'string', description: '主文件，默认 main.tex' },
      keepAux: { type: 'boolean', description: '是否保留中间文件，默认 false（删除）' },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          ok: { type: 'boolean' },
          logTail: { type: 'string' },
          auxRemoved: { type: 'array', items: { type: 'string' } },
        },
      },
      render: (_args, value) => [{
        type: 'text',
        text: `编译${value.ok ? '成功' : '失败'}\n${value.logTail}`
          + (value.auxRemoved.length ? `\n已清理中间文件：${value.auxRemoved.join('、')}` : ''),
      }],
    },
    async execute(args) {
      const dir = path.resolve(args.dir || '.')
      const file = args.file || 'main.tex'
      try {
        const out = compile(dir, file)
        const removed = cleanupAux(dir, !!args.keepAux)
        const logTail = String(out).split('\n').filter(Boolean).slice(-8).join('\n')
        return { ok: true, logTail: logTail || '（无输出）', auxRemoved: removed }
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e)
        const removed = cleanupAux(dir, !!args.keepAux)
        return { ok: false, logTail: msg.slice(0, 2000), auxRemoved: removed }
      }
    },
  }))

  // ---------- 工具 3：清理中间文件 ----------
  ctx.tools.register(defineTool({
    name: 'cleanup_latex_aux',
    description:
      '删除 LaTeX 中间文件（aux/log/toc/out/fls/fdb_latexmk/synctex.gz/xdv/bbl/blg），' +
      '仅限指定目录；keep=true 则保留。',
    parameters: {
      dir: { type: 'string', description: '报告目录，默认 .' },
      keep: { type: 'boolean', description: 'true=保留中间文件，默认 false 删除' },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          removed: { type: 'array', items: { type: 'string' } },
        },
      },
      render: (_args, value) => [{
        type: 'text',
        text: value.removed.length
          ? `已删除中间文件：${value.removed.join('、')}`
          : '未删除任何中间文件（目录不存在或已干净）',
      }],
    },
    async execute(args) {
      const dir = path.resolve(args.dir || '.')
      return { removed: cleanupAux(dir, !!args.keep) }
    },
  }))

  // ---------- 工具 4（编排）：说一句话，全流程完成 ----------
  ctx.tools.register(defineTool({
    name: 'write_experiment_report',
    description:
      '编排工具（推荐给"用 latex 写实验报告"场景）：一次调用完成 ' +
      '生成报告脚手架（规格模板）→ 编译（latexmk -xelatex -halt-on-error）→ ' +
      '默认清理中间文件。参数与 generate_latex_report 相同，另加 keepAux。',
    parameters: {
      title: { type: 'string', required: true, description: '报告题目' },
      author: { type: 'string' },
      studentId: { type: 'string' },
      group: { type: 'string' },
      date: { type: 'string' },
      sections: { type: 'array', items: { type: 'string' } },
      outputDir: { type: 'string', description: '输出目录，默认 report' },
      keepAux: { type: 'boolean', description: '保留中间文件？默认否' },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          message: { type: 'string' },
          files: { type: 'array', items: { type: 'string' } },
          compileOk: { type: 'boolean' },
        },
      },
      render: (_args, value) => [{ type: 'text', text: value.message }],
    },
    async execute(args) {
      const dir = path.resolve(args.outputDir || 'report')
      mkdirSync(dir, { recursive: true })
      const sections = args.sections?.length ? args.sections : ['第一章：背景', '第二章：实验', '结论']
      writeFileSync(path.join(dir, 'main.tex'),
        buildMainTex(args.title, args.author || '', args.studentId || '',
                    args.group || '', args.date || '', sections), 'utf8')
      const files = ['main.tex']
      sections.forEach((s, i) => {
        writeFileSync(path.join(dir, `ch${i + 1}.tex`), buildChapterTex(i + 1, s), 'utf8')
        files.push(`ch${i + 1}.tex`)
      })
      let compileOk = false
      let note = ''
      try {
        compile(dir, 'main.tex')
        compileOk = true
        note = '编译成功'
      } catch (e) {
        note = '编译失败：' + (e instanceof Error ? e.message.split('\n')[0] : String(e))
      }
      const removed = cleanupAux(dir, !!args.keepAux)
      return {
        message: `${note}。已在 ${dir} 生成：${files.join('、')}`
          + (removed.length ? `；已清理中间文件：${removed.join('、')}` : '')
          + (args.keepAux ? '；中间文件已按要求保留。' : ''),
        files,
        compileOk,
      }
    },
  }))
}
