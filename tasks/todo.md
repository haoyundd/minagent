# MinAgent 笔试改造执行清单

## Plan

- [x] 新增工具治理层，并改造 `AgentLoop` 使用它
- [x] 改造 `Session`，加入 `state`、`summary`、基础压缩能力
- [x] 改造 `TodoTool`，让 todo 数据进入 session 私有 state
- [x] 新增多 session CLI 管理命令
- [x] 新增 `ContextBuilder`，替换全量 messages 直传
- [x] 补测试：工具治理、session 隔离、context、loop
- [x] 跑完整测试并修复失败
- [x] 更新已有 `README.md` 和 `docs/AI_PROMPT_LOG.md`
- [x] 在本文末尾追加 review 小节，记录验证结果

## Execution Notes

- 目标不是堆功能，而是回应面试官反馈：工具治理、memory 治理、message 拼接治理。
- 保持不用 Agent 框架，不引入数据库、Web 服务、向量库。
- 文档只更新已有文件，不新增额外说明文档。

## Review

- 已新增工具治理层 `ToolExecutor`，统一处理工具存在性、required 参数、异常、结构化结果和 trace。
- 已将 todo 状态迁移到 `Session.state["todos"]`，不同 session 之间互不影响。
- 已新增 `ContextBuilder`，按 system、summary、state、最近消息、当前输入拼接 context。
- 已新增基础 context 压缩，旧消息进入 `Session.state["summary"]`。
- 已新增 CLI 多 session 命令：`/new`、`/sessions`、`/use <session_id>`。
- 已更新已有 `README.md` 和 `docs/AI_PROMPT_LOG.md`，对齐新版治理设计。

### Verification

```text
PY_SOURCE_PARSE_OK 16 files
python -m unittest discover -s tests
Ran 10 tests in 0.002s
OK
@('exit') | python main.py
CLI 启动并正常退出
```
