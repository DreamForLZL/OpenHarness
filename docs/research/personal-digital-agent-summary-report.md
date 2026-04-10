# OpenHarness能力初步探究结结

## 一、基础内置根据与技能

### 1. 内置工具清单

共 **34 个内置工具**，按功能分类：

**文件操作**

| 工具名             | 作用                         | 只读  |
| --------------- | -------------------------- | --- |
| `read_file`     | 读取本地文本文件                   | 是   |
| `write_file`    | 创建或覆写文本文件                  | 否   |
| `edit_file`     | 通过字符串替换编辑文件                | 否   |
| `notebook_edit` | 创建或编辑 Jupyter Notebook 单元格 | 否   |
| `glob`          | 按 glob 模式列出匹配文件            | 是   |
| `grep`          | 用正则表达式搜索文件内容               | 是   |

**Shell 与系统**

| 工具名 | 作用          | 只读  |
| -------- | ----------- | --- |
| `bash`   | 执行 Shell 命令 | 否   |
| `sleep`  | 短暂等待（轮询用）   | 是   |
| `config` | 查看/修改运行时配置  | 否   |

**Web 与搜索** 需要清理，后续使用agent-browser来做

| 工具名 | 作用 | 只读 |
| ------------ | ---------------- | --- |
| `web_search` | 网页搜索，返回标题/URL/摘要 | 是 |
| `web_fetch` | 抓取单个网页，返回精简可读文本 | 是 |

**后台任务管理**

| 工具名 | 作用 | 只读 |
| ------------- | --------------------- | --- |
| `task_create` | 创建后台 Shell 或 Agent 任务 | 否 |
| `task_get` | 查看任务详情 | 是 |
| `task_list` | 列出后台任务 | 是 |
| `task_output` | 读取任务输出日志 | 是 |
| `task_update` | 更新任务描述/进度/状态 | 否 |
| `task_stop` | 停止后台任务 | 否 |


**定时任务 (Cron)**

| 工具名 | 作用 | 只读 |
| ---------------- | ---------------- | --- |
| `cron_create` | 创建 Cron 定时任务 | 否 |
| `cron_list` | 列出已注册的 Cron 任务 | 是 |
| `cron_delete` | 删除 Cron 任务 | 否 |
| `cron_toggle` | 启用/禁用 Cron 任务 | 否 |
| `remote_trigger` | 立即手动触发一个 Cron 任务 | 否 |

**多智能体与协作**

| 工具名 | 作用 | 只读 |
| -------------- | --------------------------------------------- | --- |
| `agent` | 派生后台代理任务（支持 general-purpose、Explore、worker 等） | 否 |
| `send_message` | 向正在运行的代理任务发送后续消息 | 否 |
| `team_create` | 创建内存中的代理团队 | 否 |
| `team_delete` | 删除代理团队 | 否 |


**模式切换与 Git** 需要清理？

| 工具名 | 作用 | 只读 |
| ----------------- | --------------- | --- |
| `enter_plan_mode` | 切换到 Plan 只读模式 | 是 |
| `exit_plan_mode` | 退出 Plan 模式恢复默认 | 否 |
| `enter_worktree` | 创建 Git worktree | 否 |
| `exit_worktree` | 删除 Git worktree | 否 |


**MCP 与扩展**

| 工具名 | 作用 | 只读 |
| -------------------- | -------------- | --- |
| `list_mcp_resources` | 列出 MCP 服务器可用资源 | 是 |
| `read_mcp_resource` | 读取 MCP 资源 | 是 |
| `mcp_auth` | 配置 MCP 服务器认证 | 否 |
| `skill` | 按名称加载技能内容 | 是 |
| `tool_search` | 按名称/描述搜索可用工具 | 是 |

**其他**

| 工具名 | 作用 | 只读 |
| ------------------- | ----------------------- | --- |
| `ask_user_question` | 向用户提问等待回答 | 是 |
| `todo_write` | 向 Markdown 清单追加 TODO 项 | 否 |
| `brief` | 精简/压缩长文本输出 | 是 |
| `lsp` | LSP 语言服务器操作（跳转定义、查找引用等） | 是 |

### 2. 内置技能清单

共 **7 个内置技能**，均为 ***编码相关*** 的，后续应该要 ***全部清理*** 并放置新的：

| 技能名 | 用途 | 何时触发 |
| ---------- | ------------------ | -------------- |
| `commit` | 创建规范化 Git 提交 | 用户要求提交代码、创建 PR |
| `debug` | 系统化诊断和修复 Bug | 用户报告错误或异常行为 |
| `diagnose` | 诊断代理运行失败/退化原因 | "为什么这次运行失败了？" |
| `plan` | 设计实现方案后再编码 | 用户要求规划、设计或架构 |
| `review` | 代码审查（Bug/安全/性能/测试） | 用户要求审查代码或 PR |
| `simplify` | 简化重构，降低复杂度 | 用户要求简化或清理代码 |
| `test` | 编写和运行测试 | 用户要求写测试或提高覆盖率 |

## 二、职责约束

### 1. 职责位置

**多层系统提示词体系** — 可直接复用，注入职责描述：

```text
Layer 1: _BASE_SYSTEM_PROMPT            ← 基础系统提示词
Layer 2: build_system_prompt()          ← + 环境信息
Layer 3: build_runtime_system_prompt()  ← + 技能、CLAUDE.md、记忆
Layer 4: build_ohmo_system_prompt()     ← + SOUL.md、user.md、identity.md（可考虑在这里加，一个职责.md文件）
```

### 2. 自主思考与创建任务并执行

#### 对比参考：OpenClaw 的自主化机制

OpenClaw 已经围绕 SOUL.md 实现了完整的"自主思考 → 任务创建 → 执行 → 自我进化"闭环，核心由三个机制协同构成：

**机制一：SOUL.md 驱动自主决策**

OpenClaw 的 SOUL.md 不仅定义人格，还充当代理的"核心指令集"：

- **核心真理**（Core Truths）：引导代理在执行前进行批判性思考，优先简单方案
- **行为边界**：明确何时可自主行动、何时须请求人类批准、何种操作绝对禁止
- **自主进化**：代理可在人类指导下更新 SOUL.md 本身，实现"灵魂"的持续迭代

**机制二：Heartbeat 心跳系统**

`HEARTBEAT.md` 是 OpenClaw 实现主动思考的关键：
- 系统每 30 分钟触发一次心跳事件
- Agent 被唤醒后读取 HEARTBEAT.md，决定是否需要执行任务（检查收件箱、推进流水线等）
- 无事可做时回复 `HEARTBEAT_OK`，系统自动抑制消息，避免浪费 Token
- Agent 可通过工具动态修改 HEARTBEAT.md 内容，实现自我调度

**机制三：自我进化循环**

```text
执行任务 → 遇到错误/收获经验 → 写入 .learnings/ 目录
    → 每日反思 Cron 任务审查 .learnings/
    → 高频/重要经验提升（promote）至 MEMORY.md
    → 下次执行时自动加载，避免重复犯错
```

**配套设施：**

| 机制 | 说明 |
| ------ | ------ |
| **Cron 定时任务** | 精确时间触发（如"每天 9 点发 Review 报告"），支持主会话/隔离会话两种模式 |
| **Task Watcher** | 插件式监控异步任务状态，确保代理承诺的任务真正落地 |
| **exec / process 工具** | 后台任务执行 + 全生命周期管理（轮询进度、读日志、发输入） |
| **BASE-SOUL.md** | 多代理共享全局价值观，各代理在此基础上叠加领域个性 |

#### OpenHarness 现有可用机制

| 机制 | 来源 | 可复用程度 |
| ------ | ------ | ----------- |
| **Agent Loop** — 多轮工具调用循环 | `engine/query.py` | ✅ 核心可用 |
| **BackgroundTaskManager** — Shell/Agent 子进程 | `tasks/manager.py` | ✅ 可用 |
| **Cron 调度** — 独立守护进程，30s tick | `services/cron_scheduler.py` | ✅ 可用 |
| **TodoWrite 工具** — 会话内待办管理 | `tools/todo_write_tool.py` | ⚠️ 需增强 |
| **多代理协作** — Plan → Worker → Verification | `coordinator/` | ✅ 可借鉴 |
| **Memory 系统** — MEMORY.md + 会话存储 | `memory/` + `ohmo/session_storage.py` | ⚠️ 需增强 |
| **SOUL.md** — 人格/边界模板 | `ohmo/workspace.py` | ⚠️ 仅人格，缺决策逻辑，但我建议新增一个md文件单独管理，并且是只读权限，改就通过接口处理 |

#### OpenHarness vs OpenClaw 对比

| 维度 | OpenHarness | OpenClaw |
| ------ | ------------- | ---------- |
| SOUL.md 定位 | 人格描述 + 风格指南 | 核心指令集（人格 + 决策逻辑 + 行为边界） |
| 主动触发 | ❌ 仅响应用户输入 | ✅ Heartbeat 心跳（每 30 分钟自动唤醒） |
| 定时任务 | ✅ Cron 调度（执行 Shell 命令） | ✅ Cron（支持主会话/隔离会话，Agent 级） |
| 后台任务 | ✅ BackgroundTaskManager | ✅ exec/process 工具（自动后台化 + 生命周期管理） |
| 任务监控 | ❌ 无 | ✅ Task Watcher 插件 |
| 自我进化 | ❌ 无 | ✅ .learnings/ → 每日反思 → promote 至 MEMORY.md |
| 跨会话上下文 | ⚠️ 会话存储 + 简单恢复 | ✅ 多层记忆（Bootstrap + 语义搜索 + MEMORY.md） |
| Token 优化 | ❌ 无 | ✅ HEARTBEAT_OK 无事抑制 + 按需加载上下文 |

## 三、文本/多模态模型路由

### 现状：单一模型贯穿全程

OpenHarness 的对话循环只使用**一个模型**，由 `QueryEngine` 初始化时绑定，不会根据内容类型自动切换：

```python
class QueryEngine:
    def __init__(self, *, ..., model: str, ...):
        self._model = model  # 唯一模型参数
```

模型选择链路：

```text
ProviderProfile.default_model → Settings.model → resolve_model_setting()
    → QueryEngine._model → QueryContext.model → api_client.stream_message()
```

全程一条线，不区分文本/视觉/规划。

#### 图片处理管道已通，但共用同一模型

| 环节 | 支持 | 详情 |
| ------ | :---: | ------ |
| 消息模型 | ✅ | `ImageBlock`（base64）作为 `ContentBlock` 的一种 |
| 通道接入 | ✅ | ohmo 网关通过 `ImageBlock.from_path()` 编码图片 |
| Anthropic API | ✅ | `source.type=base64` 格式 |
| OpenAI API | ✅ | `image_url` 格式（data URI） |
| **模型路由** | ❌ | 图片和文本发给同一个模型 |

#### 现有模型切换机制（均无法满足需求）

| 机制 | 说明 | 能否满足 |
| ------ | ------ | :---: |
| **ProviderProfile** | 每个 Profile 绑定一个固定模型 | ❌ 静态配置 |
| **opusplan 别名** | plan 模式用 Opus，否则用 Sonnet | ❌ 仅按权限模式 |
| **AgentDefinition.model** | 子代理使用不同模型 | ❌ 静态预设 |

#### 对比参考：OpenClaw 的 imageModel 机制

OpenClaw 有一套成熟的方案，将模型配置拆分为三个独立维度：

```json
{
  "model":      { "primary": "MiniMax-M2.5-highspeed", "fallbacks": ["kimi-k2.5"] },
  "imageModel": { "primary": "kimi-k2.5", "fallbacks": ["gemini-2.0-flash-vision:free"] },
  "pdfModel":   { "primary": "claude-opus-4-6" }
}
```

| 场景 | OpenClaw 路由 |
| ------ | -------------- |
| 纯文本对话 | → `model.primary` |
| 用户发送图片/截图 | → `imageModel.primary`，失败走 fallbacks |
| 用户发送 PDF | → `pdfModel` → 回退 `imageModel` → 内置默认 |
| Agent 使用内置 `image` 工具 | → 工具内部调用 `imageModel` |

CLI 管理：`openclaw models set-image <model>` / `openclaw models image-fallbacks list|add|remove`

**已知局限**：`read` 工具读取本地图片时仍返回占位符，不会调用视觉模型（[Issue #48038](https://github.com/openclaw/openclaw/issues/48038)）。

## 四、上下文压缩机制

多轮对话与频繁工具调用会导致上下文迅速膨胀。OpenHarness 实现了一套完整的**自动分级压缩**系统。

### 整体架构

```text
Agent Loop 每轮开始
    │
    ▼
auto_compact_if_needed()   ← 自动触发入口
    │
    ├── should_autocompact()
    │     ├── 估算当前 token 数（字符数 ÷ 4 × 4/3 安全系数）
    │     └── 与阈值比较（context_window - 20000 - 13000）
    │
    ├── 未超阈值 → 原样返回
    │
    └── 超阈值 → 分级处理
          │
          ├── 第一级：Microcompact（无 LLM 调用）
          │     └── 清除旧工具返回内容 → "[Old tool result content cleared]"
          │     └── 仅保留最近 5 条工具结果
          │     └── 若清理后低于阈值 → 完成
          │
          └── 第二级：Full Compact（调用 LLM 总结）
                └── 将旧消息发给 LLM 生成结构化摘要
                └── 保留最近 6 条消息原文
                └── 用摘要替换所有旧消息
```

### 压缩前是否保存原始数据？

**结论：不保存。** 压缩操作直接在内存中的 `messages` 列表上就地修改（`mutated in place`），被清除的工具返回内容和被总结替换的旧消息**没有任何备份机制**。

具体来说：

- **Microcompact**：`ToolResultBlock.content` 被直接替换为 `"[Old tool result content cleared]"`，原始内容丢失
- **Full Compact**：旧消息被摘要替换，原始消息列表被丢弃
- **Session Snapshot**：`save_snapshot` 在 Agent Loop **结束后**才调用，保存的是压缩后的消息，不是压缩前的完整记录

这意味着：如果 `read_file` 读取了一个 500 行的文件，经过 Microcompact 后该返回内容就永久丢失了——无论是内存中还是磁盘上。

所以上下文压缩机制我们还是需要大改一番，否则审计的要求不过关，或者可以参考learn-claude-code的压缩方式。

## 五、不支持http调用接口

这个可以自己实现，不是难事
