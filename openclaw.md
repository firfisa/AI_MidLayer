---
link: https://github.com/openclaw/openclaw
---
> 提问：
> 帮我具体分析一下为什么openclaw可以实现几乎像人类一样强的行动能力（普通的AI可能只能做一两步，而openclaw却可以完成整个目标的活动），他为什么会消耗如此庞大的token，这种强的行动能力是由什么技术塑造出来的。

**回答了以下问题**
- 为什么openclaw可以实现几乎像人类一样强的行动能力
- 为什么会消耗如此庞大的token
- 这种强的行动能力是由哪些技术塑造出来的。

## Gemini
通过分析 `openclaw` 的源代码，我们可以从技术架构、交互逻辑和数据流向三个维度来揭示它为何拥有如此强大的行动能力，以及为何会消耗海量的 Token。

### 1. 为什么 OpenClaw 拥有“类人”的强行动能力？
普通的 AI（如 ChatGPT 网页版）通常是**问答式（Turn-based）**的：你问，它答，结束。而 OpenClaw 的核心在于它构建了一个**递归的代理循环（Recursive Agent Loop）**，使其具备了“自主性”。

#### A. OODA 循环架构 (Observe-Orient-Decide-Act)
OpenClaw 不仅仅是生成文本，它在一个闭环中运行，代码中的 `src/agents/pi-embedded-runner.ts` 和 `src/agents/pi-embedded-runner/run.ts` 揭示了这个核心逻辑：
1. **观察 (Observe):** 它获取当前环境的状态（通过 `bash` 获取文件列表，通过 `browser` 获取网页内容，或者通过 `screenshot` 获取屏幕视觉信息）。
2. **判断 (Orient):** 它将“目标”与“当前状态”进行对比，判断还差什么。
3. **决策 (Decide):** 基于大模型（如 Claude 3.5 Sonnet 或 GPT-4o）的推理能力，决定下一步调用哪个工具（Tool）。
4. **行动 (Act):** **真正地执行**代码或指令（Execute），而不是假装执行。
5. **反馈 (Feedback):** 它会读取工具执行的**真实输出**（stdout/stderr/截图）。如果报错了，它会看到错误信息，并尝试自我修正。
**代码证据：**
在 `src/agents/pi-embedded-runner/run/attempt.ts` 中，可以看到代理在每次尝试（attempt）中都会执行工具，捕获结果，并将结果追加到历史记录中，供下一次推理使用。

#### B. 真实的操作系统权限 (OS-Native Tools)
普通 AI 只能在沙盒里写代码给你看，而 OpenClaw 集成了真实的系统接口。
- **终端控制 (`bash-tools.ts`):** 它可以像程序员一样在终端执行任何命令。
- **浏览器控制 (`browser-tools.ts`, `browser/pw-tools-core.ts`):** 它使用 Playwright 等技术自动化控制浏览器，能点击、输入、滚动，甚至处理复杂的网页交互。
- **视觉能力 (`image-tool.ts`):** 它可以“看”到屏幕或图片，这让它能处理那些无法用纯文本描述的 UI 交互。

### 2. 为什么它会消耗如此庞大的 Token？
OpenClaw 的高 Token 消耗是其“强上下文”和“自我修正”机制的必然代价。

#### A. 累积的执行历史 (Accumulated Context)
为了实现“连续行动”，AI 必须记住它之前做过的**每一步**。
- **场景：** 假设任务是“安装一个软件并配置”。
- **第1步：** AI 执行 `install` 命令 -> 返回 50 行安装日志（包含进度条、文本）。
- **第2步：** AI 需要根据这 50 行日志判断是否成功。如果你不把这 50 行发回给 AI，它就不知道发生了什么。
- **后果：** 随着任务进行，历史记录（History）呈线性甚至指数级增长。每次新的请求，都要把之前所有的对话、代码、**以及冗长的终端输出**全部重新发送给大模型。
**代码证据：**
`src/agents/compaction.ts` 和 `src/agents/context-window-guard.ts` 显示，OpenClaw 必须不断地检测上下文是否溢出，并尝试“压缩”历史，但这本身就说明了原始数据的庞大。

#### B. 视觉信息的 Token 开销 (Vision Costs)
OpenClaw 具备多模态能力。当它进行网页浏览或处理 UI 时，它会发送截图。
- 一张高分辨率的屏幕截图或网页快照，在转化为 Token 发送给大模型（如 GPT-4o 或 Claude 3.5）时，通过 Base64 编码传输，会占用成千上万的 Token。
- 如果它在一个任务中截了 10 次图，Token 消耗量是惊人的。

#### C. 庞大的系统提示词 (Huge System Prompt)
为了让 AI 能够准确地使用工具、遵守安全规范、按特定格式输出，OpenClaw 会在每次对话的最开始注入一个非常详尽的“系统提示词（System Prompt）”。
- 这个提示词包含了所有可用工具的定义（JSON Schema）、操作系统的环境信息（Env Vars）、当前目录结构等。
- **代码证据：** `src/agents/pi-embedded-runner/system-prompt.ts` 展示了它是如何动态构建这个庞大的初始指令集的。

### 3. 这种能力是由什么技术塑造出来的？
#### A. ReAct (Reasoning + Acting) 提示工程模式
这是核心思想。技术上，它利用了 LLM 的 **Function Calling (工具调用)** 能力。
- 模型被训练为：当遇到需要行动的场景时，输出一个特定的 JSON 结构（如 `{ "tool": "exec", "code": "ls -la" }`）。
- OpenClaw 的运行时（Runtime）拦截这个 JSON，在本地执行，然后将结果封装成 `ToolOutput` 扔回给模型。

#### B. 多模态大语言模型 (VLM)
OpenClaw 的强大很大程度上依赖于底座模型（如 Claude 3.5 Sonnet）的进化。这些模型具备了极强的代码理解能力和视觉理解能力，能够从一张截图中识别出“登录按钮在哪里”，或者从一段报错日志中推断出“缺少依赖库”。

#### C. 运行时沙箱与持久化 (Session & Persistence)
OpenClaw 通过 `src/memory/` 模块实现了会话的持久化。这使得它不仅能完成瞬间的任务，还能在长达几小时甚至几天的任务中保持状态（例如，它知道昨天下载的文件放在了哪里）。它通过 SQLite 或文件系统 (`src/memory/sqlite.ts`) 记录了完整的思维链。

### 总结
OpenClaw 之所以强，是因为它**把 LLM 从一个“说话者”变成了一个“操作者”**。它通过**递归循环**赋予了 AI 时间维度的连续性，通过**系统工具**赋予了 AI 空间维度的操作权。
**代价**就是，为了维持这种“像人一样连续思考和操作”的幻觉，它必须在每一次微小的行动中，都向云端大模型同步整个世界的当前状态（历史、屏幕、文件），从而导致了极高的 Token 消耗。

## GPT
下面按“它为什么能做成整件事 / 为什么这么烧 token / 这种行动能力由哪些技术塑造”把 OpenClaw 拆开讲（基于它的官方仓库与文档）。

---

### 1) 为什么 OpenClaw 能“像人类一样把目标做完”
很多“普通 AI”停在 1–2 步，本质原因通常不是模型不聪明，而是**缺少一个能持续运行、能落地执行、能保存状态的执行系统**。OpenClaw 把这三件事都补齐了：

#### A. 它不是“一问一答”，而是“可持续的 agent loop”
OpenClaw 的官方文档把它的运行链路描述得很直白：一次真实运行是 _intake → context assembly → model inference → tool execution → streaming replies → persistence_，并且**每个 session 内是串行、可持续的 run**。这意味着模型在同一次目标中可以不断“看结果→再行动→再看结果”，直到完成或超时。 ([OpenClaw](https://docs.openclaw.ai/concepts/agent-loop "Agent Loop - OpenClaw"))
同时，OpenClaw 的 agent loop 会把模型侧的工具调用/assistant 输出以事件流形式桥接回来（tool stream、assistant stream、lifecycle），形成稳定的“行动—观察—再行动”闭环。 ([OpenClaw](https://docs.openclaw.ai/concepts/agent-loop "Agent Loop - OpenClaw"))

#### B. 它给了模型**真正可控、可复现**的“手和眼”
OpenClaw 强的关键不是“会想”，而是“能动”：
- **浏览器工具**：OpenClaw 不是让模型瞎猜网页，而是提供“快照 + 引用（ref）”机制：先把页面转成文本快照并标注可操作元素 ref，然后点击/输入都引用 ref（而不是脆弱的 CSS selector）。这大幅提高了长链路任务的成功率与可恢复性。 ([OpenClaw](https://docs.openclaw.ai/tools/browser "Browser (OpenClaw-managed) - OpenClaw"))
- 其浏览器控制内部是 **CDP + Playwright**：控制面稳定、动作确定性强（可列 tab、focus、click/type、snapshot、PDF、screenshot 等）。 ([OpenClaw](https://docs.openclaw.ai/tools/browser "Browser (OpenClaw-managed) - OpenClaw"))
- **Exec / Node / Skills**：它不止浏览器，还能跑命令（可在 sandbox / gateway / node 上执行）、连接陪伴设备节点、加载技能扩展，让“行动空间”接近真实电脑工作流。 ([OpenClaw](https://docs.openclaw.ai/tools/exec "Exec Tool - OpenClaw"))
> 你感受到的“像人类一样强”，很大比例来自：**它把真实世界的操作接口产品化成工具**，模型只需要在工具空间里做决策。

#### C. 它把“状态”当一等公民：workspace + session + 记忆
- OpenClaw 强制把 agent 的工作目录收敛到 workspace，并注入一组可编辑的引导文件（AGENTS.md / SOUL.md / TOOLS.md / USER.md 等），相当于“长期工作说明书 + 偏好 + 操作约束”。 ([OpenClaw](https://docs.openclaw.ai/concepts/agent "Agent Runtime - OpenClaw"))
- Session 以 JSONL 方式落盘保存，保证跨消息的连续性。 ([OpenClaw](https://docs.openclaw.ai/concepts/agent "Agent Runtime - OpenClaw"))
- 还有语义记忆检索（memory_search / memory_get），用 embedding 在 MEMORY.md 与 memory/*.md 里查片段，让 agent 能“翻笔记”而不是全靠上下文硬塞。 ([OpenClaw](https://docs.openclaw.ai/concepts/memory "Memory - OpenClaw"))
- 当对话变长，它会做 compaction：把较早内容总结成一条摘要并保留最近消息，避免上下文爆掉。 ([OpenClaw](https://docs.openclaw.ai/concepts/compaction "Compaction - OpenClaw"))

#### D. 还能“分身”：多 agent 路由 + 子 agent
OpenClaw 支持把不同渠道/场景路由到不同 agent（不同 workspace、模型、工具权限、sandbox 策略）。 ([OpenClaw](https://docs.openclaw.ai/concepts/multi-agent "Multi-Agent Routing - OpenClaw"))
并且有 session 工具可以 spawn 子 agent 跑任务，再把结果回传（还支持一定轮数的“乒乓”协作）。 ([OpenClaw](https://docs.openclaw.ai/concepts/session-tool "Session Tools - OpenClaw"))
这就是为什么它更像“一个能干活的执行系统”，而不是“一个会聊天的模型”。

---

### 2) 为什么 OpenClaw 会消耗**巨量 token**
token 大，通常不是单一原因，而是多个“结构性开销”叠加：

#### A. 每次调用都要带上“系统 prompt + 工作区文件 + 技能列表 + 工具 schema”
OpenClaw 的系统 prompt 是拼装出来的：基础 prompt + skills prompt + bootstrap context + per-run overrides。 ([OpenClaw](https://docs.openclaw.ai/concepts/agent-loop "Agent Loop - OpenClaw"))
而且它会注入 workspace 文件（并对大文件截断，默认每文件最多 20000 chars）。 ([OpenClaw](https://docs.openclaw.ai/concepts/system-prompt "System Prompt - OpenClaw"))
更“隐形”的大头是：**工具 schema（JSON）也算上下文 token**，即使你看不到。官方示例里 tool schemas 约 31,988 chars（~7,997 tok），这还没算对话历史。 ([OpenClaw](https://docs.openclaw.ai/concepts/context "Context - OpenClaw"))

#### B. 工具输出会非常长，尤其是浏览器 snapshot / 日志 / 大段 toolResult
浏览器快照本质是把页面结构转成文本（还要包含 refs），如果页面复杂，快照自然变长；OpenClaw 还提供“interactive/compact/depth/efficient”等模式来控制密度，本质就是在压 token。 ([OpenClaw](https://docs.openclaw.ai/tools/browser "Browser (OpenClaw-managed) - OpenClaw"))

#### C. 它是“多轮工具调用”系统：一次目标 ≈ 多次 LLM 往返
你以为是“一个回答”，其实可能是：
**模型 → tool → 模型 → tool → … → 最终回复**，每一轮都要重新发送相当多的上下文（哪怕有缓存也有边界）。

#### D. 缓存 TTL 过期会导致“重新写入整段 prompt”
官方专门做了 session pruning，原因之一就是：某些提供商的 prompt caching 只在 TTL 内有效；一旦会话 idle 超过 TTL，下一次请求可能要重新 cache 全量 prompt，成本会猛增。 ([OpenClaw](https://docs.openclaw.ai/concepts/session-pruning "Session pruning - OpenClaw"))

---

### 3) OpenClaw 这种“强行动能力”到底是由什么技术塑造的
用一句话概括：**“Agent Loop + 可执行工具 + 状态管理/记忆压缩 + 扩展生态”**。
对应到更具体的技术构件：
1. **工程化的 Agent Loop（串行、可中断、可观测）**：session lane 串行化、防 race、事件流桥接、超时控制。 ([OpenClaw](https://docs.openclaw.ai/concepts/agent-loop "Agent Loop - OpenClaw"))
2. **确定性的操作接口**：浏览器采用 CDP + Playwright，快照-引用式操作（refs）减少“点错/找不到元素”的失败模式。 ([OpenClaw](https://docs.openclaw.ai/tools/browser "Browser (OpenClaw-managed) - OpenClaw"))
3. **工具系统与扩展（Skills / Plugins）**：技能清单注入 prompt，引导模型按需 read 对应 SKILL.md，再调用工具；技能还带安装/依赖/ gating 机制，变成可管理的软件包。 ([OpenClaw](https://docs.openclaw.ai/concepts/system-prompt "System Prompt - OpenClaw"))
4. **记忆与压缩**：语义检索式记忆（embedding + chunk）降低“把所有历史硬塞进上下文”的依赖；compaction 与 pruning 则是应对上下文膨胀与缓存失效的工程补丁。 ([OpenClaw](https://docs.openclaw.ai/concepts/memory "Memory - OpenClaw"))
5. **多 agent / 子 agent**：把复杂目标拆给不同 agent（不同模型与权限），并通过 session 工具进行协作式回传。 ([OpenClaw](https://docs.openclaw.ai/concepts/multi-agent "Multi-Agent Routing - OpenClaw"))

---

### 4) 如果你想“同样强，但少烧 token”，可以从这几处下手
- **控制浏览器快照体积**：启用 `snapshot --efficient` 或把默认设为 efficient，减少每轮上下文注入量。 ([OpenClaw](https://docs.openclaw.ai/tools/browser "Browser (OpenClaw-managed) - OpenClaw"))
- **清理/收敛 TOOLS.md 与注入文件**：系统支持查看每个注入文件与工具 schema 的 token 占比（/context list/detail），把最大的那几个压下去最有效。 ([OpenClaw](https://docs.openclaw.ai/concepts/context "Context - OpenClaw"))
- **减少工具/技能数量**：工具 schema 和 skills 列表都会进入 prompt（而且 schema 是隐形大头）。 ([OpenClaw](https://docs.openclaw.ai/concepts/context "Context - OpenClaw"))
- **启用 compaction / session pruning**：让长会话“总结+修剪 toolResult”，并降低 TTL 过期后的重新 cache 成本。 ([OpenClaw](https://docs.openclaw.ai/concepts/compaction "Compaction - OpenClaw"))
- **用多 agent 分层**：日常用便宜模型，深度任务路由到更强模型（官方 multi-agent routing 就是为这个场景设计的）。 ([OpenClaw](https://docs.openclaw.ai/concepts/multi-agent "Multi-Agent Routing - OpenClaw"))

---

如果你愿意，我也可以按一个具体任务（比如“自动登录某网站完成一笔操作并发消息确认”）给你画出 OpenClaw 在 agent loop 里会走哪些 tool call、每步大致会产生哪些 token 大头，以及该怎么配置把成本砍下来。


