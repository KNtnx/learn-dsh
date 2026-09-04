// ============================================================
// hello-plugin.ts —— 跟做官方 "Your first plugin"（最小插件形态）
// 官方原文：docs/user/develop/basic/index.md
// 插件 = 一个导出 name + apply 的模块；apply 在挂载时执行。
// 本文件与官方教程示例一致（console.log('[hello-plugin] plugin loaded!')），
// 用于验证：dsh web --patch 加载后终端打印该行（真实运行证据
// 见 evidence/ch4/07_first_plugin.txt）。
// ============================================================

export const name = 'hello-plugin'

export function apply() {
  console.log('[hello-plugin] plugin loaded!')
}
