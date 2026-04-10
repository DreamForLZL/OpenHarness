# 基于 OpenHarness 构建个人数字代理 — 技术可行性调研报告

> **调研日期**：2026-04-09
> **调研人**：luzhiliang
> **项目版本**：openharness-ai 0.1.5

---

## 一、调研目标

评估 OpenHarness 项目作为基础框架，开发"个人数字代理"的可行性。重点关注三项需求：

| # | 需求 | 描述 |
|---|------|------|
| 1 | **职责约束** | 用户为代理配置"职责"，代理围绕职责工作，主动拒绝超范围请求 |
| 2 | **自主思考与任务执行** | 代理围绕职责自动进行思考、创建相关任务并执行 |
| 3 | **文本/多模态模型路由** | 文本对话用文本模型，图片理解用多模态模型，按需自动切换 |
| 4 | **企业级审计日志** | 记录大模型调用、工具调用、决策链路，满足审计合规要求 |

---

## 二、项目概况

OpenHarness 是一个开源的 Python AI 编程助手 CLI，定位类似 Claude Code 的开源替代。

### 2.1 项目结构

```text
OpenHarness/
├── src/openharness/       # 核心引擎（Agent Loop、工具、权限、提示词等）
├── ohmo/                  # 个人代理产品层（工作区、人格、网关）
├── frontend/              # React TUI 前端
├── scripts/               # 安装脚本
└── tests/                 # 测试
```

### 2.2 核心子系统

| 子系统 | 路径 | 职责 |
|--------|------|------|
| Engine | `engine/` | 对话循环（Agent Loop）、流式工具调用 |
| Tools | `tools/` | 43+ 内置工具（文件、Shell、搜索、Web、MCP 等） |
| Prompts | `prompts/` | 系统提示词组装（基础人格 + 运行时上下文） |
| Permissions | `permissions/` | 权限模式（5 种）、路径/命令规则、Hook、交互审批 |
| Coordinator | `coordinator/` | 多智能体定义（6 种内置子代理）与团队注册 |
| Tasks | `tasks/` | 后台任务管理（Shell/Agent 子进程） |
| Memory | `memory/` | 持久化记忆（MEMORY.md） |
| Channels | `channels/` | IM/HTTP 消息信道（Telegram、Discord、企微、HTTP API 等） |
| Config | `config/` | 多层配置（CLI > 环境变量 > JSON > 默认值） |
| Services | `services/` | 上下文压缩、Cron 定时调度 |
| API | `api/` | 20+ LLM 厂商的 API 客户端（Anthropic、OpenAI、DeepSeek、Qwen 等） |

> 以上路径均相对于 `src/openharness/`。

### 2.3 ohmo — 个人代理产品层

ohmo 是在 OpenHarness 引擎之上构建的"个人代理"封装：

- **工作区** (`~/.ohmo/`)：`soul.md`（人格）、`user.md`（用户画像）、`identity.md`、`memory/`、`sessions/`
- **网关服务**：MessageBus + ChannelManager + 会话池，支持多通道同时接入
- **人格系统**：通过 Markdown 模板定义代理的性格、边界、风格
- **入口命令**：`ohmo` CLI（含 `gateway`、`soul`、`user`、`memory` 等子命令）

### 2.4 内置工具清单

共 **34 个内置工具**，按功能分类：

**文件操作**

| 工具名 | 作用 | 只读 |
|--------|------|:----:|
| `read_file` | 读取本地文本文件 | 是 |
| `write_file` | 创建或覆写文本文件 | 否 |
| `edit_file` | 通过字符串替换编辑文件 | 否 |
| `notebook_edit` | 创建或编辑 Jupyter Notebook 单元格 | 否 |
| `glob` | 按 glob 模式列出匹配文件 | 是 |
| `grep` | 用正则表达式搜索文件内容 | 是 |

**Shell 与系统**

| 工具名 | 作用 | 只读 |
|--------|------|:----:|
| `bash` | 执行 Shell 命令 | 否 |
| `sleep` | 短暂等待（轮询用） | 是 |
| `config` | 查看/修改运行时配置 | 否 |

**Web 与搜索**

| 工具名 | 作用 | 只读 |
|--------|------|:----:|
| `web_search` | 网页搜索，返回标题/URL/摘要 | 是 |
| `web_fetch` | 抓取单个网页，返回精简可读文本 | 是 |

**后台任务管理**

| 工具名 | 作用 | 只读 |
|--------|------|:----:|
| `task_create` | 创建后台 Shell 或 Agent 任务 | 否 |
| `task_get` | 查看任务详情 | 是 |
| `task_list` | 列出后台任务 | 是 |
| `task_output` | 读取任务输出日志 | 是 |
| `task_update` | 更新任务描述/进度/状态 | 否 |
| `task_stop` | 停止后台任务 | 否 |

**定时任务 (Cron)**

| 工具名 | 作用 | 只读 |
|--------|------|:----:|
| `cron_create` | 创建 Cron 定时任务 | 否 |
| `cron_list` | 列出已注册的 Cron 任务 | 是 |
| `cron_delete` | 删除 Cron 任务 | 否 |
| `cron_toggle` | 启用/禁用 Cron 任务 | 否 |
| `remote_trigger` | 立即手动触发一个 Cron 任务 | 否 |

**多智能体与协作**

| 工具名 | 作用 | 只读 |
|--------|------|:----:|
| `agent` | 派生后台代理任务（支持 general-purpose、Explore、worker 等） | 否 |
| `send_message` | 向正在运行的代理任务发送后续消息 | 否 |
| `team_create` | 创建内存中的代理团队 | 否 |
| `team_delete` | 删除代理团队 | 否 |

**模式切换与 Git**

| 工具名 | 作用 | 只读 |
|--------|------|:----:|
| `enter_plan_mode` | 切换到 Plan 只读模式 | 是 |
| `exit_plan_mode` | 退出 Plan 模式恢复默认 | 否 |
| `enter_worktree` | 创建 Git worktree | 否 |
| `exit_worktree` | 删除 Git worktree | 否 |

**MCP 与扩展**

| 工具名 | 作用 | 只读 |
|--------|------|:----:|
| `list_mcp_resources` | 列出 MCP 服务器可用资源 | 是 |
| `read_mcp_resource` | 读取 MCP 资源 | 是 |
| `mcp_auth` | 配置 MCP 服务器认证 | 否 |
| `skill` | 按名称加载技能内容 | 是 |
| `tool_search` | 按名称/描述搜索可用工具 | 是 |

**其他**

| 工具名 | 作用 | 只读 |
|--------|------|:----:|
| `ask_user_question` | 向用户提问等待回答 | 是 |
| `todo_write` | 向 Markdown 清单追加 TODO 项 | 否 |
| `brief` | 精简/压缩长文本输出 | 是 |
| `lsp` | LSP 语言服务器操作（跳转定义、查找引用等） | 是 |

### 2.5 内置技能清单

共 **7 个内置技能**，均为 Markdown 提示模板，通过 `skill` 工具加载后注入代理上下文：

| 技能名 | 用途 | 何时触发 |
|--------|------|---------|
| `commit` | 创建规范化 Git 提交 | 用户要求提交代码、创建 PR |
| `debug` | 系统化诊断和修复 Bug | 用户报告错误或异常行为 |
| `diagnose` | 诊断代理运行失败/退化原因 | "为什么这次运行失败了？" |
| `plan` | 设计实现方案后再编码 | 用户要求规划、设计或架构 |
| `review` | 代码审查（Bug/安全/性能/测试） | 用户要求审查代码或 PR |
| `simplify` | 简化重构，降低复杂度 | 用户要求简化或清理代码 |
| `test` | 编写和运行测试 | 用户要求写测试或提高覆盖率 |

每个技能本质是一个详细的 **工作流指南**，包含：
- **When to use** — 触发条件
- **Workflow** — 分步操作流程
- **Rules** — 必须遵循的约束

### 2.6 自定义扩展方式

#### 方式一：用户技能目录（最简单，运行时生效）

在 `~/.openharness/skills/` 下创建子目录，放入 `SKILL.md` 即可：

```text
~/.openharness/skills/
└── my-custom-skill/
    └── SKILL.md         # Markdown 格式的技能定义
```

`SKILL.md` 支持 YAML frontmatter 或 heading 解析：

```markdown
---
name: my-custom-skill
description: 我的自定义技能描述
---

# 我的自定义技能

## When to use
当用户要求...

## Workflow
1. 第一步
2. 第二步

## Rules
- 规则一
- 规则二
```

**无需重启**，下次代理调用 `skill(name="my-custom-skill")` 时自动加载。

#### 方式二：插件系统（完整扩展）

创建插件目录，包含 `plugin.json` 清单文件：

```text
my-plugin/
├── plugin.json          # 插件清单
├── skills/              # 插件贡献的技能
│   └── custom-skill/
│       └── SKILL.md
├── hooks.json           # 插件贡献的 Hook
└── agents/              # 插件贡献的子代理定义
```

```json
{
  "name": "my-plugin",
  "version": "1.0.0",
  "description": "我的企业插件",
  "enabled_by_default": true,
  "skills_dir": "skills",
  "hooks_file": "hooks.json"
}
```

插件可以贡献：技能、斜杠命令、子代理定义、Hook。

#### 方式三：自定义工具（代码级）

继承 `BaseTool` 抽象类：

```python
from pydantic import BaseModel, Field
from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult

class MyToolInput(BaseModel):
    query: str = Field(description="查询内容")

class MyTool(BaseTool):
    name = "my_tool"
    description = "我的自定义工具"
    input_model = MyToolInput

    def is_read_only(self, arguments: MyToolInput) -> bool:
        return True

    async def execute(self, arguments: MyToolInput, context: ToolExecutionContext) -> ToolResult:
        result = do_something(arguments.query)
        return ToolResult(output=result)
```

然后在 `create_default_tool_registry()` 中注册，或通过插件动态注册。

#### 方式四：MCP 工具（外部服务）

通过 MCP（Model Context Protocol）配置外部工具服务器，代理自动发现和调用。

---

## 三、需求分析

### 3.1 需求一：职责约束

#### 现有可用机制

**多层系统提示词体系** — 可直接复用，注入职责描述：

```text
Layer 1: _BASE_SYSTEM_PROMPT            ← 基础人格
Layer 2: build_system_prompt()          ← + 环境信息
Layer 3: build_runtime_system_prompt()  ← + 技能、CLAUDE.md、记忆
Layer 4: build_ohmo_system_prompt()     ← + SOUL.md、user.md、identity.md
```

**子代理定义系统** — 可借鉴其"按角色限制行为"的模式：

```python
class AgentDefinition(BaseModel):
    name: str
    system_prompt: str | None = None       # 独立系统提示
    tools: list[str] | None = None         # 工具白名单
    disallowed_tools: list[str] | None = None  # 工具黑名单
    permission_mode: str | None = None     # 权限模式
    max_turns: int | None = None           # 最大回合数
```

**SOUL.md 模板** — 已有"Boundaries"概念，但仅是自然语言软约束：

```markdown
## Boundaries
- Private things stay private.
- When in doubt, ask before acting externally.
```

**权限模式** — 5 种（`default` / `acceptEdits` / `bypassPermissions` / `plan` / `dontAsk`），控制"能不能操作"而非"该不该做"。

#### 差距

| 维度 | 现状 | 目标 | 差距 |
|------|------|------|------|
| 职责定义 | SOUL.md 自然语言 | 结构化配置（范围、边界、拒绝策略） | 🔴 需要新建 |
| 职责执行 | 依赖 LLM 自行判断 | 程序级校验 + LLM 判断 | 🟡 需要增强 |
| 拒绝机制 | 无 | 识别超范围 → 礼貌拒绝 → 可选转交 | 🔴 需要新建 |
| 工具约束 | AgentDefinition 的白/黑名单 | 按职责动态过滤 | 🟡 可扩展 |

#### 建议方案：Prompt 软约束 + Hook 硬约束

1. **新增 `duty.json`**（`~/.ohmo/duty.json`）：
   ```json
   {
     "role": "财务数据分析助手",
     "scope": ["财务报表分析", "数据可视化", "Excel/CSV 处理"],
     "boundaries": ["不涉及法律咨询", "不进行投资建议"],
     "allowed_tools": ["read_file", "write_file", "bash", "grep", "glob"],
     "rejection_style": "polite"
   }
   ```
2. **修改 `build_ohmo_system_prompt`**：注入职责描述
3. **新增 PreToolUse Hook**：工具白名单硬约束
4. **可选**：轻量模型做职责校验前置判断

**预估工作量**：3-5 天

---

### 3.2 需求二：自主思考与任务执行

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
|------|------|
| **Cron 定时任务** | 精确时间触发（如"每天 9 点发 Review 报告"），支持主会话/隔离会话两种模式 |
| **Task Watcher** | 插件式监控异步任务状态，确保代理承诺的任务真正落地 |
| **exec / process 工具** | 后台任务执行 + 全生命周期管理（轮询进度、读日志、发输入） |
| **BASE-SOUL.md** | 多代理共享全局价值观，各代理在此基础上叠加领域个性 |

#### OpenHarness 现有可用机制

| 机制 | 来源 | 可复用程度 |
|------|------|-----------|
| **Agent Loop** — 多轮工具调用循环 | `engine/query.py` | ✅ 核心可用 |
| **BackgroundTaskManager** — Shell/Agent 子进程 | `tasks/manager.py` | ✅ 可用 |
| **Cron 调度** — 独立守护进程，30s tick | `services/cron_scheduler.py` | ✅ 可用 |
| **TodoWrite 工具** — 会话内待办管理 | `tools/todo_write_tool.py` | ⚠️ 需增强 |
| **多代理协作** — Plan → Worker → Verification | `coordinator/` | ✅ 可借鉴 |
| **Memory 系统** — MEMORY.md + 会话存储 | `memory/` + `ohmo/session_storage.py` | ⚠️ 需增强 |
| **SOUL.md** — 人格/边界模板 | `ohmo/workspace.py` | ⚠️ 仅人格，缺决策逻辑 |

#### OpenHarness vs OpenClaw 对比

| 维度 | OpenHarness | OpenClaw |
|------|-------------|----------|
| SOUL.md 定位 | 人格描述 + 风格指南 | 核心指令集（人格 + 决策逻辑 + 行为边界） |
| 主动触发 | ❌ 仅响应用户输入 | ✅ Heartbeat 心跳（每 30 分钟自动唤醒） |
| 定时任务 | ✅ Cron 调度（执行 Shell 命令） | ✅ Cron（支持主会话/隔离会话，Agent 级） |
| 后台任务 | ✅ BackgroundTaskManager | ✅ exec/process 工具（自动后台化 + 生命周期管理） |
| 任务监控 | ❌ 无 | ✅ Task Watcher 插件 |
| 自我进化 | ❌ 无 | ✅ .learnings/ → 每日反思 → promote 至 MEMORY.md |
| 跨会话上下文 | ⚠️ 会话存储 + 简单恢复 | ✅ 多层记忆（Bootstrap + 语义搜索 + MEMORY.md） |
| Token 优化 | ❌ 无 | ✅ HEARTBEAT_OK 无事抑制 + 按需加载上下文 |

#### 差距

| 维度 | 现状 | 目标（参考 OpenClaw） | 差距 |
|------|------|------|------|
| SOUL.md 增强 | 人格描述 | + 决策逻辑 + 行为边界 + 自主行动规则 | 🟡 需要增强 |
| 心跳机制 | 无 | HEARTBEAT.md + 定时唤醒 + 无事抑制 | 🔴 需要新建 |
| 自我进化 | 无 | .learnings/ + 每日反思 + 经验提升 | 🔴 需要新建 |
| Cron 增强 | 仅 Shell 命令 | 支持 Agent 级任务 + 隔离会话 | 🟡 需要增强 |
| 任务监控 | 无 | Task Watcher 确保任务落地 | 🔴 需要新建 |
| Token 优化 | 无 | 按需唤醒 + 无事抑制 | 🟡 需要增强 |

#### 建议方案：参考 OpenClaw，Heartbeat + 自我进化 + 增强 Cron

1. **增强 SOUL.md** — 从纯人格描述升级为"核心指令集"：
   ```markdown
   ## Core Truths
   - 行动前先思考，优先简单方案
   - 不确定就承认，不要编造

   ## Autonomous Rules
   - 可自主执行：文件整理、数据分析、定期报告
   - 须请求批准：发送外部消息、删除文件、修改配置
   - 绝对禁止：访问敏感系统、修改 SOUL.md（除非用户明确要求）

   ## Heartbeat Checklist
   - 检查待处理任务队列
   - 查看是否有新的用户消息
   - 审查昨日执行结果，更新优先级
   ```

2. **新增 HEARTBEAT.md + 心跳服务**：
   ```text
   [Cron 每 30 分钟触发] → 加载 SOUL.md + HEARTBEAT.md + MEMORY.md
       → Agent 判断是否有事要做
       → 有：执行任务 → 更新 MEMORY.md / 任务状态
       → 无：返回 HEARTBEAT_OK → 抑制通知，节省 Token
   ```
   基于现有 `cron_scheduler.py` 扩展，从"执行 Shell 命令"升级为"唤醒 Agent 会话"。

3. **新增自我进化循环**：
   ```text
   执行任务 → 记录经验/错误至 ~/.ohmo/learnings/
       → [每日 Cron] 反思 .learnings/ 内容
       → 高频经验提升至 MEMORY.md
       → 重要教训更新 SOUL.md 的行为规则
   ```

4. **增强 Cron 调度** — 支持 Agent 级任务：
   - 当前：`cron_scheduler.py` 仅执行 Shell 命令（`create_shell_subprocess`）
   - 目标：新增 `execute_agent_job`，在 Cron 触发时启动 Agent 会话，传入 prompt

5. **新增 Task Watcher** — 确保异步任务落地：
   - 监控 `BackgroundTaskManager` 中任务状态
   - 超时未完成的任务自动提醒 Agent 或用户

**预估工作量**：7-14 天（参考 OpenClaw 的设计可降低试错成本）

---

### 3.3 需求三：文本/多模态模型路由

#### 现状：单一模型贯穿全程

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
|------|:---:|------|
| 消息模型 | ✅ | `ImageBlock`（base64）作为 `ContentBlock` 的一种 |
| 通道接入 | ✅ | ohmo 网关通过 `ImageBlock.from_path()` 编码图片 |
| Anthropic API | ✅ | `source.type=base64` 格式 |
| OpenAI API | ✅ | `image_url` 格式（data URI） |
| **模型路由** | ❌ | 图片和文本发给同一个模型 |

#### 现有模型切换机制（均无法满足需求）

| 机制 | 说明 | 能否满足 |
|------|------|:---:|
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
|------|--------------|
| 纯文本对话 | → `model.primary` |
| 用户发送图片/截图 | → `imageModel.primary`，失败走 fallbacks |
| 用户发送 PDF | → `pdfModel` → 回退 `imageModel` → 内置默认 |
| Agent 使用内置 `image` 工具 | → 工具内部调用 `imageModel` |

CLI 管理：`openclaw models set-image <model>` / `openclaw models image-fallbacks list|add|remove`

**已知局限**：`read` 工具读取本地图片时仍返回占位符，不会调用视觉模型（[Issue #48038](https://github.com/openclaw/openclaw/issues/48038)）。

#### OpenHarness vs OpenClaw 对比

| 维度 | OpenHarness | OpenClaw |
|------|-------------|----------|
| 模型配置 | 单一 `model` 字段 | `model` + `imageModel` + `pdfModel` 三维度 |
| 回退链 | 无 | 每个维度 `primary` + `fallbacks` |
| 图片消息管道 | ✅ 已通 | ✅ 已通 |
| 内容类型自动路由 | ❌ | ✅ |
| 内置视觉工具 | ❌ | ✅ `image` 工具 |
| CLI 管理 | 无 | `openclaw models set-image` 等 |
| 默认视觉模型 | 无 | 按 API 厂商自动选择 |

#### 差距

| 维度 | 差距 |
|------|------|
| 多模态消息管道 | ✅ 无需改动 |
| 按内容类型路由模型 | 🔴 需要新建 |
| 模型回退链 | 🔴 需要新建 |
| 内置视觉工具 | 🟡 可扩展 |

#### 建议方案：参考 OpenClaw imageModel 设计

1. **Settings 新增多模型配置**：
   ```json
   {
     "model": { "primary": "deepseek-chat", "fallbacks": ["kimi-k2.5"] },
     "imageModel": { "primary": "gpt-5.4", "fallbacks": ["kimi-k2.5"] }
   }
   ```
   兼容简写：`"model": "deepseek-chat", "image_model": "gpt-5.4"`

2. **run_query 循环内增加内容检测**：存在 `ImageBlock` 时临时切换到 `imageModel`

3. **可选：新增 `image` 工具**：Agent 可主动调用视觉模型分析本地图片

**预估工作量**：2-3 天（基础路由）；含回退链和 `image` 工具约 4-5 天

---

## 四、综合评估

### 4.1 能力覆盖矩阵

| 所需能力 | 现有支持度 | 说明 |
|----------|:---:|------|
| LLM 对话与推理 | ⬛⬛⬛⬛⬛ 100% | 多模型、流式输出、上下文压缩 |
| 工具调用与执行 | ⬛⬛⬛⬛⬛ 100% | 43+ 内置工具、MCP、并行执行 |
| 系统提示词管理 | ⬛⬛⬛⬛⬛ 100% | 多层叠加、运行时动态构建 |
| 多通道接入 | ⬛⬛⬛⬛⬛ 100% | Telegram、Discord、企微、HTTP API 等 |
| 多模态消息管道 | ⬛⬛⬛⬛⬜ 80% | ImageBlock 管道完整，缺模型路由 |
| 人格与身份 | ⬛⬛⬛⬛⬜ 80% | SOUL/IDENTITY/USER，缺结构化职责 |
| 会话管理 | ⬛⬛⬛⬛⬜ 80% | 持久化与恢复，缺跨会话目标追踪 |
| 权限控制 | ⬛⬛⬛⬛⬜ 80% | 5 种模式 + Hook，缺职责级过滤 |
| 后台任务 | ⬛⬛⬛⬜⬜ 60% | Shell/Agent 子进程 + Cron，缺任务队列 |
| 任务自动创建与执行 | ⬛⬛⬜⬜⬜ 40% | Agent Loop + BackgroundTask，缺编排层 |
| 职责约束 | ⬛⬜⬜⬜⬜ 20% | 仅 SOUL.md 软约束 |
| 文本/多模态模型路由 | ⬛⬜⬜⬜⬜ 20% | 仅 opusplan，无内容类型路由 |
| 自主思考 | ⬛⬜⬜⬜⬜ 20% | 无主动触发机制 |

### 4.2 总体结论

**OpenHarness + ohmo 是一个优秀的基础框架**。核心基础设施（Agent Loop、工具系统、提示词、多通道、API 适配）非常完善，三项需求均可在此基础上实现：

| 需求 | 可行性 | 框架复用率 | 新增开发量 |
|------|:---:|:---:|------|
| 职责约束 | ✅ 可行 | ~60% | 3-5 天 |
| 自主思考与任务执行 | ✅ 可行 | ~40% | 7-14 天 |
| 文本/多模态模型路由 | ✅ 可行 | ~80% | 2-5 天 |

---

## 五、推荐开发路线图

```text
Phase 1（第 1 周）：职责约束 + 模型路由
├── 设计 duty.json 配置格式
├── 修改 build_ohmo_system_prompt 注入职责
├── 新增 PreToolUse Hook 工具白名单过滤
├── Settings / QueryContext 新增 image_model 字段
├── run_query 内增加 ImageBlock 检测与模型切换
└── 测试：超范围拒绝 + 图片消息使用多模态模型

Phase 2（第 2-3 周）：自主任务管理
├── 设计 TaskQueue 数据模型与持久化
├── 实现 TaskQueue CRUD API
├── 新增 task_create / task_list / task_update 工具
└── 测试：代理可创建、查看、更新任务

Phase 3（第 3-4 周）：自主思考循环
├── 实现 ThinkingLoop 服务（Cron 触发）
├── 设计反思提示模板
├── 实现 TaskExecutor（队列 → Agent Loop）
├── 增强 Memory（thinking_log + task_state）
└── 测试：代理能自主反思、创建任务并执行

Phase 4（第 4 周+）：打磨与集成
├── 配置界面优化（CLI wizard 或 Web UI）
├── 执行结果自动验证（复用 verification 子代理）
├── 模型回退链 + image 工具
├── 异常处理与容错
└── 文档与使用指南
```

---

## 六、上下文压缩机制

多轮对话与频繁工具调用会导致上下文迅速膨胀。OpenHarness 实现了一套完整的**自动分级压缩**系统。

### 6.1 整体架构

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
          ├── 第一级：Microcompact（无 LLM 调用，毫秒级）
          │     └── 清除旧工具返回内容 → "[Old tool result content cleared]"
          │     └── 仅保留最近 5 条工具结果
          │     └── 若清理后低于阈值 → 完成
          │
          └── 第二级：Full Compact（调用 LLM 总结）
                └── 将旧消息发给 LLM 生成结构化摘要
                └── 保留最近 6 条消息原文
                └── 用摘要替换所有旧消息
```

### 6.2 Microcompact（轻量压缩）

不调用 LLM，直接清除旧的工具返回内容。

**可压缩的工具类型**（`COMPACTABLE_TOOLS`）：

| 工具 | 说明 |
|------|------|
| `read_file` | 读文件 |
| `bash` | Shell 命令 |
| `grep` | 搜索 |
| `glob` | 文件查找 |
| `web_search` | 网页搜索 |
| `web_fetch` | 网页抓取 |
| `edit_file` | 编辑文件 |
| `write_file` | 写文件 |

**规则**：保留最近 5 条工具结果（`keep_recent=5`），更早的结果内容替换为 `"[Old tool result content cleared]"`。工具调用本身（tool_use block）不被清除，只清除返回值。

### 6.3 Full Compact（LLM 总结压缩）

当 Microcompact 不足以将 token 压到阈值以下时触发。

**流程**：
1. 先执行一轮 Microcompact
2. 将消息分为「旧消息」（待总结）和「近期消息」（保留原文，默认 6 条）
3. 将旧消息 + 压缩提示词发给 LLM，要求生成结构化摘要
4. 摘要替换所有旧消息，近期消息接在后面

**压缩提示词要求 LLM 输出的摘要结构**：
1. Primary Request and Intent — 所有用户请求的完整细节
2. Key Technical Concepts — 讨论的技术框架和模式
3. Files and Code Sections — 涉及的文件、代码、行号
4. Errors and Fixes — 所有错误及修复方式
5. Problem Solving — 解决思路（有效的和无效的）
6. All User Messages — 保留用户原始消息措辞
7. Pending Tasks — 尚未完成的工作
8. Current Work — 压缩前正在做的事
9. Optional Next Step — 最合理的下一步

### 6.4 阈值计算

```text
autocompact_threshold = context_window - MAX_OUTPUT_TOKENS(20000) - BUFFER(13000)

例如 Claude Sonnet（200K）:
  threshold = 200,000 - 20,000 - 13,000 = 167,000 tokens
```

Token 估算使用简单启发式：`len(text) / 4 × 4/3`（字符数除以 4 再乘以安全系数）。

### 6.5 容错机制

| 机制 | 说明 |
|------|------|
| 连续失败上限 | Full Compact 连续失败 3 次后停止尝试（`MAX_CONSECUTIVE_AUTOCOMPACT_FAILURES=3`） |
| 空摘要保护 | 若 LLM 返回空摘要，放弃压缩，保留原始消息 |
| 最少保留量 | `preserve_recent=6`，至少保留 6 条近期消息不被压缩 |
| 工具结果最少保留 | `keep_recent=5`，至少保留 5 条最新工具结果 |

### 6.6 用户手动触发

除自动机制外，用户还可以通过斜杠命令手动触发：

| 命令 | 说明 |
|------|------|
| `/compact [N]` | 手动压缩，保留最近 N 条消息（默认 6） |
| `/summary [N]` | 查看最近 N 条消息的文本摘要 |

### 6.7 对个人数字代理的影响

| 场景 | 影响 | 建议 |
|------|------|------|
| 长时间自主执行 | 多轮工具调用后自动压缩，可能丢失任务链中间状态 | 关键中间结果应写入 Memory 持久化，不依赖对话上下文 |
| 定时自主思考 | 每次 Cron 触发是新会话，无上下文膨胀问题 | 需通过 Memory/TaskQueue 传递跨会话状态 |
| 网关通道消息 | 多个用户并发会话各自独立压缩 | 合理设置 `preserve_recent` 避免重要上下文被压缩 |

### 6.8 压缩前是否保存原始数据？

**结论：不保存。** 压缩操作直接在内存中的 `messages` 列表上就地修改（`mutated in place`），被清除的工具返回内容和被总结替换的旧消息**没有任何备份机制**。

具体来说：
- **Microcompact**：`ToolResultBlock.content` 被直接替换为 `"[Old tool result content cleared]"`，原始内容丢失
- **Full Compact**：旧消息被摘要替换，原始消息列表被丢弃
- **Session Snapshot**：`save_snapshot` 在 Agent Loop **结束后**才调用，保存的是压缩后的消息，不是压缩前的完整记录

这意味着：如果 `read_file` 读取了一个 500 行的文件，经过 Microcompact 后该返回内容就永久丢失了——无论是内存中还是磁盘上。

---

## 七、需求四：企业级审计日志

### 7.1 审计需求定义

企业级智能助手需要完整的审计追踪，包括三个维度：

| # | 审计维度 | 需记录的内容 |
|---|---------|-------------|
| 1 | **大模型调用** | 模型名称、系统提示词、用户消息、工具列表、max_tokens、延迟、input/output tokens、完整回复、stop_reason |
| 2 | **工具/函数调用** | 工具名称、入参、权限决策、耗时、出参/异常、Hook 执行结果 |
| 3 | **决策链路** | 规划步骤、中间推理、分支选择、压缩事件、子代理调度 |

### 7.2 现有记录机制盘点

#### 7.2.1 Session Snapshot（会话快照）

**文件**：`src/openharness/services/session_storage.py`

每次用户交互完成后保存到 `~/.openharness/data/sessions/`：

```json
{
  "session_id": "abc123",
  "cwd": "/path/to/project",
  "model": "claude-sonnet-4-6",
  "system_prompt": "You are OpenHarness...",
  "messages": ["/* 完整消息列表（压缩后） */"],
  "usage": { "input_tokens": 1234, "output_tokens": 567 },
  "created_at": 1712678400.0,
  "summary": "用户第一条消息的前 80 字符",
  "message_count": 15
}
```

| 已记录 | 未记录 |
|--------|--------|
| model 名称 | 每次 API 调用的延迟 |
| system_prompt | 每次调用的独立 token 用量（仅有累计值） |
| 消息列表（含 tool_use + tool_result） | 压缩前的原始消息 |
| 累计 usage（input/output tokens） | 重试次数和重试延迟 |
| | stop_reason |

#### 7.2.2 Python logging（debug 级别日志）

**文件**：`src/openharness/engine/query.py`

```python
log.debug("tool_call start: %s id=%s", tool_name, tool_use_id)
log.debug("permission check: %s read_only=%s path=%s cmd=%s", ...)
log.debug("executing %s ...", tool_name)
log.debug("executed %s in %.2fs err=%s output_len=%d", tool_name, elapsed, ...)
```

| 已记录（debug 级别） | 未记录 |
|---------------------|--------|
| 工具名称、ID | 工具入参完整内容 |
| 权限检查结果 | 工具输出完整内容 |
| 执行耗时 | 大模型 API 请求/响应详情 |
| 是否出错、输出长度 | 决策推理过程 |

**问题**：这些是 `log.debug` 级别，默认不输出，且是非结构化文本，不适合审计查询。

#### 7.2.3 Stream Events（流事件）

**文件**：`src/openharness/engine/stream_events.py`

Agent Loop 的 `run_query` 通过 `yield` 产出事件流：

| 事件类型 | 包含信息 |
|---------|---------|
| `AssistantTextDelta` | 增量文本 |
| `AssistantTurnComplete` | 完整消息 + UsageSnapshot |
| `ToolExecutionStarted` | 工具名 + 入参 |
| `ToolExecutionCompleted` | 工具名 + 输出 + 是否出错 |
| `ErrorEvent` | 错误消息 |
| `StatusEvent` | 重试等状态信息 |

这些事件在 UI 层被消费后**没有持久化**，仅用于实时渲染。

#### 7.2.4 Hook 系统

**文件**：`src/openharness/hooks/`

提供 `PRE_TOOL_USE` 和 `POST_TOOL_USE` 两个钩子事件：

```python
# PRE_TOOL_USE payload
{"tool_name": "bash", "tool_input": {"command": "ls"}, "event": "pre_tool_use"}

# POST_TOOL_USE payload
{"tool_name": "bash", "tool_input": {"command": "ls"},
 "tool_output": "...", "tool_is_error": False, "event": "post_tool_use"}
```

Hook 可配置为 `HttpHookDefinition`（发送 HTTP 请求），理论上可以将工具调用事件推送到外部审计系统。但：
- 仅覆盖工具调用，不覆盖大模型调用
- 没有 `PRE_LLM_CALL` / `POST_LLM_CALL` 类似钩子
- 没有覆盖压缩事件

### 7.3 审计差距分析

```text
审计需求              现有覆盖度        差距
─────────────────────────────────────────────────────────
大模型调用            ▓▓░░░ ~40%      缺少：每次调用的延迟、独立 token
                                      用量、stop_reason、完整请求/响应、
                                      重试记录
─────────────────────────────────────────────────────────
工具/函数调用          ▓▓▓░░ ~60%      部分覆盖：debug 日志有耗时和错误，
                                      Hook 有入参出参，但都不持久化/
                                      非结构化
─────────────────────────────────────────────────────────
决策链路              ▓░░░░ ~20%      严重不足：无规划步骤记录、无分支
                                      选择记录、压缩事件仅 log.info、
                                      子代理调度无追踪
─────────────────────────────────────────────────────────
原始数据保全          ░░░░░  0%       压缩前的原始消息/工具返回内容
                                      无任何保存
```

### 7.4 建设方案

#### 层级一：审计事件模型

定义统一的审计事件结构：

```python
@dataclass
class AuditEvent:
    event_id: str           # UUID
    session_id: str
    timestamp: float        # Unix timestamp
    event_type: str         # llm_call | tool_call | decision | compact | hook
    duration_ms: float
    payload: dict           # 事件特定数据
    parent_event_id: str    # 父事件 ID（用于构建决策树）
```

各类型 payload 示例：

```python
# event_type = "llm_call"
{
    "model": "claude-sonnet-4-6",
    "system_prompt_hash": "sha256:abc...",
    "message_count": 15,
    "tools_provided": ["bash", "read_file"],
    "max_tokens": 4096,
    "input_tokens": 1234,
    "output_tokens": 567,
    "stop_reason": "end_turn",
    "response_text_preview": "前 200 字符...",
    "retry_count": 0,
}

# event_type = "tool_call"
{
    "tool_name": "bash",
    "tool_input": {"command": "ls -la"},
    "permission_decision": "allowed",
    "tool_output_preview": "前 500 字符...",
    "tool_output_hash": "sha256:def...",
    "is_error": False,
    "pre_hook_result": "pass",
    "post_hook_result": "pass",
}

# event_type = "compact"
{
    "compact_type": "microcompact",
    "messages_before": 45,
    "messages_after": 7,
    "tokens_before": 180000,
    "tokens_after": 35000,
    "tools_cleared": ["read_file#id1", "bash#id2"],
    "archive_path": "/audit/sessions/xxx/pre-compact-001.jsonl",
}

# event_type = "decision"
{
    "decision_type": "sub_agent_dispatch",
    "reasoning_preview": "前 300 字符...",
    "chosen_branch": "use bash to check file",
    "alternatives_considered": ["read_file", "grep"],
}
```

#### 层级二：注入点

| 注入位置 | 文件 | 记录内容 |
|---------|------|---------|
| `api_client.stream_message()` 前后 | `engine/query.py:104-127` | LLM 调用请求参数 + 延迟 + token + 回复 |
| `_execute_tool_call()` 内 | `engine/query.py:253-268` | 工具调用（已有计时，需持久化） |
| `auto_compact_if_needed()` 前后 | `engine/query.py:91-97` | 压缩事件 + 原始消息归档 |
| `compact_conversation()` 内 | `services/compact/__init__.py:293-374` | 压缩前消息快照 |
| Hook 执行后 | `hooks/executor.py:64-78` | Hook 执行结果 |
| 子代理调度处 | `coordinator/` | 子代理启动/完成/失败 |

#### 层级三：存储后端

建议分层存储：

```text
热数据（近 7 天）    → SQLite / PostgreSQL    ← 结构化查询、仪表盘
温数据（7-90 天）    → JSONL 文件（按会话）   ← 归档、全文搜索
冷数据（90 天+）     → 对象存储 / 压缩归档    ← 合规保留
```

压缩前原始消息归档方案：

```text
~/.openharness/audit/
├── sessions/
│   └── {session_id}/
│       ├── events.jsonl            # 审计事件流
│       ├── pre-compact-001.jsonl   # 第 1 次压缩前完整消息
│       ├── pre-compact-002.jsonl   # 第 2 次压缩前完整消息
│       └── system-prompt.txt       # 系统提示词快照
└── index.db                        # SQLite 索引
```

### 7.5 工作量评估

| 任务 | 工作量 | 优先级 |
|------|:------:|:------:|
| 定义 AuditEvent 数据模型 | 1 天 | P0 |
| 实现 AuditLogger 接口（内存 + JSONL 后端） | 2 天 | P0 |
| LLM 调用注入点（query.py 包装 stream_message） | 1 天 | P0 |
| 工具调用注入点（提升 debug 为结构化记录） | 1 天 | P0 |
| 压缩前原始消息归档 | 1 天 | P0 |
| Hook 执行记录 | 0.5 天 | P1 |
| 决策链路追踪（parent_event_id 关联） | 2 天 | P1 |
| 子代理调度追踪 | 1 天 | P1 |
| SQLite 索引 + 查询 API | 2 天 | P2 |
| 审计仪表盘（Web UI） | 3-5 天 | P2 |
| 数据生命周期管理（热/温/冷分层） | 1 天 | P2 |
| **合计** | **约 15-17 天** | |

---

## 八、风险与注意事项

| 风险 | 影响 | 缓解措施 |
|------|:---:|----------|
| 职责约束依赖 LLM 判断，可能不够可靠 | 中 | Prompt 软约束 + Hook 硬约束双层防线 |
| 自主执行可能产生不可逆操作 | 高 | 默认 plan 模式（只读），高风险操作需审批 |
| 跨会话上下文丢失 | 中 | 增强 Memory 持久化，每次思考循环加载完整上下文 |
| Cron 自主思考消耗 Token | 低 | 轻量模型做初步筛选，仅必要时调用主模型 |
| 文本模型不支持图片导致调用失败 | 中 | 检测到图片自动切换 + 回退链 + 文本化降级 |
| 项目版本较早（0.1.5），API 可能变化 | 中 | 密切关注上游变更，模块化封装减少耦合 |
| 长任务链中间状态因压缩丢失 | 中 | 关键结果主动写入 Memory/文件，不依赖对话上下文 |
| 审计日志影响性能 | 低 | 异步写入、批量刷盘、JSONL 追加写入最小化 I/O |
| 审计数据量膨胀 | 中 | 分层存储 + 生命周期管理 + 工具输出仅存摘要和哈希 |

---

## 九、附录

### A. 关键文件索引

| 文件 | 说明 |
|------|------|
| `src/openharness/engine/query.py` | Agent Loop 核心实现（run_query） |
| `src/openharness/engine/query_engine.py` | QueryEngine 对话引擎 |
| `src/openharness/engine/messages.py` | 消息模型（TextBlock / ImageBlock / ToolUseBlock） |
| `src/openharness/prompts/system_prompt.py` | 基础系统提示词 |
| `src/openharness/prompts/context.py` | 运行时提示词组装 |
| `src/openharness/coordinator/agent_definitions.py` | 子代理定义系统（6 种内置代理） |
| `src/openharness/tasks/manager.py` | 后台任务管理 |
| `src/openharness/services/cron_scheduler.py` | Cron 定时调度 |
| `src/openharness/tools/base.py` | 工具抽象与注册 |
| `src/openharness/permissions/` | 权限管理 |
| `src/openharness/channels/impl/manager.py` | 通道管理器 |
| `src/openharness/api/openai_client.py` | OpenAI 兼容客户端（含图片序列化） |
| `src/openharness/api/registry.py` | LLM Provider 注册表（20+ 厂商） |
| `src/openharness/config/settings.py` | 主配置（Settings / ProviderProfile） |
| `ohmo/workspace.py` | ohmo 工作区管理 |
| `ohmo/prompts.py` | ohmo 提示词组装 |
| `ohmo/gateway/service.py` | ohmo 网关服务 |
| `ohmo/gateway/runtime.py` | ohmo 会话运行时池 |
| `ohmo/gateway/bridge.py` | ohmo 消息桥接 |
| `src/openharness/services/compact/__init__.py` | 上下文压缩（Microcompact + Full Compact） |
| `src/openharness/services/token_estimation.py` | Token 数量估算 |
| `src/openharness/services/session_storage.py` | 会话快照存储 |
| `src/openharness/services/session_backend.py` | 会话后端接口 |
| `src/openharness/hooks/events.py` | Hook 事件定义 |
| `src/openharness/hooks/executor.py` | Hook 执行引擎 |
| `src/openharness/engine/stream_events.py` | Agent Loop 流事件类型 |
| `src/openharness/prompts/claudemd.py` | CLAUDE.md 发现与加载 |

### B. Agent Loop 伪代码

```python
while turn_count < max_turns:
    auto_compact_if_needed(messages)
    response = LLM.stream(system_prompt, messages, tools)
    messages.append(response)

    if not response.has_tool_calls:
        return  # 对话结束

    for tool_call in response.tool_calls:
        pre_hook(tool_call)            # Hook 检查
        permission_check(tool_call)     # 权限校验
        result = tool.execute(tool_call.input)
        post_hook(tool_call, result)

    messages.append(tool_results_as_user_message)
    turn_count += 1
```

### C. 系统提示词详细组装流程

系统提示词在**每次用户输入前**重新构建（不是一次性生成），因此能动态反映最新的记忆、技能和上下文。

#### 阶段一：基础层（`build_system_prompt`）

由 `src/openharness/prompts/system_prompt.py` 负责：

```text
┌─────────────────────────────────────────────────────────────┐
│ _BASE_SYSTEM_PROMPT（或 custom_prompt 整体替换）             │
│                                                             │
│  • 身份声明（"You are OpenHarness..."）                     │
│  • 系统规则（工具权限、prompt injection 防护等）             │
│  • 任务执行原则（先读再改、不过度工程化等）                  │
│  • 操作安全（可逆/不可逆操作的判断准则）                    │
│  • 工具使用规范（专用工具优先于 Bash）                      │
│  • 语气风格（简洁、先说结论、不说废话）                     │
├─────────────────────────────────────────────────────────────┤
│ # Environment                                               │
│  • OS / Architecture / Shell / Working directory            │
│  • Date / Python version / Git branch                       │
└─────────────────────────────────────────────────────────────┘
```

**关键代码**：`build_system_prompt(custom_prompt, cwd)` — 若提供 `custom_prompt` 则整体替换基础提示。

#### 阶段二：运行时层（`build_runtime_system_prompt`）

由 `src/openharness/prompts/context.py` 负责，在基础层之上叠加动态内容：

```text
┌─ 基础层（阶段一输出）─────────────────────────────────────┐
├─────────────────────────────────────────────────────────────┤
│ # Session Mode（若 fast_mode 开启）                         │
│  "Prefer concise replies, minimal tool use..."              │
├─────────────────────────────────────────────────────────────┤
│ # Reasoning Settings                                        │
│  • Effort: low / medium / high                              │
│  • Passes: 1-N                                              │
├─────────────────────────────────────────────────────────────┤
│ # Available Skills（动态扫描 skills/ 目录）                  │
│  • plan: "软件架构师..."                                     │
│  • commit: "生成规范提交..."                                 │
│  • ...                                                      │
├─────────────────────────────────────────────────────────────┤
│ # Project Instructions（CLAUDE.md / .claude/rules/*.md）     │
│  从 cwd 向上逐级搜索，加载所有匹配文件                       │
├─────────────────────────────────────────────────────────────┤
│ # Issue Context（若存在 .openharness/issue.md）              │
│ # Pull Request Comments（若存在 .openharness/pr_comments.md）│
├─────────────────────────────────────────────────────────────┤
│ # Memory（MEMORY.md 索引 + 按用户输入语义检索相关记忆文件）   │
│  • load_memory_prompt() → MEMORY.md 前 N 行                │
│  • find_relevant_memories(user_prompt) → 相关记忆内容        │
└─────────────────────────────────────────────────────────────┘
```

**关键代码**：`build_runtime_system_prompt(settings, cwd, latest_user_prompt, ...)`
- `latest_user_prompt` 用于**语义检索相关记忆**，因此每次用户输入都会影响提示词内容。

#### 阶段三：ohmo 人格层（`build_ohmo_system_prompt`）

由 `ohmo/prompts.py` 负责，仅在 ohmo 模式下使用：

```text
┌─ 基础层（_BASE_SYSTEM_PROMPT，注意不经过阶段二）─────────────┐
├─────────────────────────────────────────────────────────────┤
│ # Additional Instructions（extra_prompt，可注入职责）        │
├─────────────────────────────────────────────────────────────┤
│ # ohmo Soul（~/.ohmo/soul.md）                              │
│  • Core truths / Boundaries / Vibe / Continuity             │
├─────────────────────────────────────────────────────────────┤
│ # ohmo Identity（~/.ohmo/identity.md）                      │
│  • Name / Kind / Vibe / Signature                           │
├─────────────────────────────────────────────────────────────┤
│ # User Profile（~/.ohmo/user.md）                           │
│  • 用户信息 / 偏好 / 项目 / 工作习惯                       │
├─────────────────────────────────────────────────────────────┤
│ # First-Run Bootstrap（~/.ohmo/BOOTSTRAP.md，仅首次存在）    │
├─────────────────────────────────────────────────────────────┤
│ # ohmo Workspace                                            │
│  • 工作区根路径 / 会话隔离说明                              │
├─────────────────────────────────────────────────────────────┤
│ # ohmo Memory（~/.ohmo/memory/MEMORY.md + 记忆文件）        │
├─────────────────────────────────────────────────────────────┤
│ # Project Memory（可选，仅 include_project_memory=True）     │
└─────────────────────────────────────────────────────────────┘
```

#### 阶段四：网关运行时选择

ohmo 网关的 `_runtime_system_prompt` 方法决定使用哪条路径：

```python
# ohmo/gateway/runtime.py
def _runtime_system_prompt(self, bundle, latest_user_prompt):
    settings = bundle.current_settings()
    if not hasattr(settings, "system_prompt"):
        return build_ohmo_system_prompt(...)    # → 阶段三
    return build_runtime_system_prompt(...)      # → 阶段二（叠加技能、记忆等）
```

#### 阶段五：子代理提示词

子代理（`AgentDefinition`）有独立的系统提示词，完全替换上述流程：

| 子代理 | 系统提示词核心内容 |
|--------|-------------------|
| general-purpose | "完成任务并报告要点" |
| Explore | "只读模式，禁止修改文件，搜索并分析代码" |
| Plan | "只读模式，设计实现方案，输出步骤和关键文件" |
| worker | "执行编码任务，运行测试，提交代码" |
| verification | "验证实现正确性，尝试破坏它，输出 PASS/FAIL/PARTIAL" |

#### 各场景提示词组成一览

| 场景 | 提示词路径 | 组成部分 |
|------|-----------|----------|
| **CLI 直接使用** | 阶段一 → 阶段二 | 基础人格 + 环境 + 技能 + CLAUDE.md + 记忆 |
| **ohmo TUI** | 阶段三 → 阶段二 | 基础人格 + SOUL + IDENTITY + USER + BOOTSTRAP + 工作区 + ohmo 记忆 + 技能 + CLAUDE.md + 项目记忆 |
| **ohmo 网关（通道消息）** | 阶段三 或 阶段二 | 同上，由网关运行时动态选择 |
| **子代理** | 阶段五 | AgentDefinition.system_prompt（独立，不继承父级） |
| **每轮工具调用** | 不变 | 同一 system_prompt 贯穿整个 Agent Loop，不会逐轮变化 |
| **新一轮用户输入** | 重新构建 | 每次 submit_message 前重新调用 build_runtime_system_prompt，更新记忆和上下文 |

### D. 模型选择链路

```text
ProviderProfile.default_model          # Profile 预设模型
    → Settings.model                   # 用户配置覆盖
    → resolve_model_setting()          # 别名解析（sonnet → claude-sonnet-4-6）
    → QueryEngine.__init__(model=...)  # 引擎初始化绑定
    → QueryContext.model               # 每轮对话使用
    → api_client.stream_message()      # 发送至 LLM API

备注：
- 全程一条链路，不区分文本/视觉/规划
- opusplan 是唯一条件分支（按权限模式选 opus 或 sonnet）
- 子代理可通过 AgentDefinition.model 覆盖，但也是静态预设
```
