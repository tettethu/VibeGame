# Godot PR #4 后续范围

当前切片见[规格](../spec/godot-pr4-sync.md)。以下事项沿用 PR 的实验性支持边界，不包含在本次同步中。

- [x] done | 验证维护者六项修复与最新主分支兼容 | 完成标准：74 项基础测试通过，Godot 4.7.2 实际命令验证通过，合并代码与 GitHub 自动合并结果一致。
- [ ] open | Godot 多 agent 构建流程 | 完成标准：设计、架构、编码、审计和运行验收均可在 Godot 项目中完整执行。
- [ ] open | Godot 美术管线与 Dashboard 资源预览 | 完成标准：产出资源可导入 Godot，Dashboard 可预览并更新对应资源。
- [ ] open | Godot 发布与 HTML5 导出 | 完成标准：发布命令生成并验证可运行的导出产物。
- [ ] open | 与 Phaser RuntimeClock 的逐帧语义对齐 | 完成标准：记录两种引擎的推进契约，并通过对应的运行时回归测试。
- [ ] open | 独立安装包包含 Godot 模板 | 完成标准：非 editable 安装可以在不依赖源码 checkout 的情况下初始化并运行 Godot 项目。
