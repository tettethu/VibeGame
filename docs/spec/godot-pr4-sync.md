# Godot PR #4 上游同步与修复验收

状态：done
当前切片：保留维护者已推送到 PR 分支的修复，完成与最新 `origin/main` 的合并并验证现有命令。

## 依据与范围

- 用户要求查看 [PR #4](https://github.com/tettethu/VibeGame/pull/4) 及[维护者评论](https://github.com/tettethu/VibeGame/pull/4#issuecomment-6688018917)，拉取最新仓库并提交。
- PR 原分支为 `207f196`，最新上游为 `1005dcb`。开始时工作区已经处于合并这两个版本的状态；暂存结果与 GitHub 的 `origin/pr4-merge` 完全一致。
- 接受并验证维护者的六项修复：拒绝带 `Origin` 的运行时请求、检查所有脚本和场景并拒绝失败启动、暂停时保留输入、运行和检查前导入资源、安全初始化及严格的继续超时、原测试的说明文档。
- 沿用现有 Python CLI、Godot 模板和目录结构，不增加依赖。非目标及后续范围见[待办](../todos/godot-pr4-sync.md)。

## 契约

- `vibegame godot init PATH --name NAME --lang en` 创建空入口场景和运行时桥接；存在目标文件时必须显式使用 `--force`。
- `vibegame godot check PATH` 与 `vibegame check PATH` 导入资源，在包含 autoload 的上下文中检查 `.gd` 和 `.tscn`，错误导致非零退出。
- `vibegame godot run PATH --port auto -b` 启动运行时。现有 `vibegame play` 通过 `/api/runtime/*` 发送命令，不增加 Godot 专用调用接口。
- 带 `Origin` 的运行时请求返回 403，不转发到 Godot；本机 CLI 请求继续可用。
- 暂停时的输入在推进帧时交给游戏；`continue` 未按时完成则失败。
- `vibegame close PATH` 结束自己跟踪的进程并清理运行时登记。
- 本次不修改前端，不增加前端业务计算，不发送 GitHub 评论或私信。本地未跟踪的信件不纳入提交。

## 改动与验收

- 现有暂存的 62 个文件是上游主分支合并结果；新增本规格及对应待办记录验收范围。
- 执行 `.venv/bin/python -m pytest tests/base -q`，覆盖 Godot 回归、图像响应解析和 Dashboard 编辑冲突检查。
- 使用本机 Godot 4.7.2 在临时项目中执行初始化、两种检查入口、后台运行、状态、快照、输入、暂停/推进、表达式求值、截图和关闭，确认进程及端口释放。
- 执行 `git diff --cached --check`，核对合并仅保留 PR 原改动和本次验收文档，完成合并提交并推送原 PR 分支。

## 验收结果

- 2026-11-07，Python 3.12.14、Godot 4.7.2：`.venv/bin/python -m pytest tests/base -q` 全部通过，结果为 `74 passed in 41.49s`，包含 14 项 Godot 测试。
- 初始化生成空入口场景；重复初始化拒绝覆盖既有文件。两种检查入口均通过。
- 在检查后新增 PNG 并由脚本 `preload()`，直接启动运行时成功导入，求值返回图片宽度 8。
- 暂停时点击、Space 按键和 `ui_accept` action 均不立即送达；各推进 5 帧后，计数器分别增加 1。
- 实际运行时的 `eval`、`set`、快照、console 读写与清空、刷新、暂停、播放和退出控制模式均正常。
- 实际 HTTP 请求带 `Origin` 时返回 403，响应无 `Access-Control-Allow-Origin`。
- 无窗口截图明确失败；有窗口截图生成尺寸为 1280×720 的 PNG。空场景截图只有背景符合模板预期。
- 两种模式关闭后无残留游戏进程，运行时端口释放，登记清空。临时证据保留于仓库内被忽略的 `tmp-godot-pr4-76qi4jaj/`。
- 查看自动分配端口的日志时需要 `godot run --logs --port <实际端口>`；`Expression` 中访问 autoload 使用 `get_node("/root/VibeGameBridge")`。这些属于现有命令用法，本次不变更接口。
- 合并代码与 `origin/pr4-merge` 完全一致，原有六项修复全部保留，未发现与原设计冲突；本次额外改动仅为规格与待办文档。
