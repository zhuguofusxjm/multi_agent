# 运营商统一智能体平台 — 架构学习指南

本文档帮助你理解整个 Agent 框架的核心原理，按请求链路逐层讲解。

---

## 请求链路总览

```
用户消息 → chat() → supervisor.handle() → _route() → _prepare_agent_input() → agent.execute() → skill.run()
                                                                                          ↓
                                                                               _update_state() → 响应返回
```

---

## 1. 入口层：`app/api/chat.py`

```python
session = session_manager.get_or_create(request.session_id)
result = await supervisor.handle(session, request.message)
```

- `session_manager` 管理所有用户会话，用 session_id 区分不同用户
- 如果 session_id 为空，创建新会话；否则加载已有会话继续多轮
- 一个 session 贯穿整个对话生命周期

---

## 2. 调度层：`app/core/supervisor.py`

### 2.1 handle() — 主流程

```python
async def handle(self, session, user_message):
    # 1) 记录用户消息到全局历史
    session.global_history.append(Message(role="user", content=user_message))

    # 2) 路由：让LLM判断用户意图属于哪个Agent
    routing = await self._route(session)

    # 3) 获取目标Agent的局部状态
    agent_state = session.get_agent_state(target)

    # 4) 裁剪上下文，组装Agent输入
    agent_messages = self._prepare_agent_input(session, agent_state, routing)

    # 5) 执行Agent
    result = await agent.execute(agent_messages, agent_state)

    # 6) 更新状态
    self._update_state(session, target, agent_state, user_message, result, routing)

    return result
```

### 2.2 _route() — 意图路由

**作用**：一次LLM调用，判断用户消息应该交给哪个Agent处理。

**输入**：最近10轮全局历史  
**输出**：
```json
{
  "target_agent": "design_agent",   // 目标Agent
  "is_followup": false,             // 是否追问/修改上一轮结果
  "context_summary": "用户想设计..."  // 传给子Agent的摘要
}
```

**类比**：前台接待员，听完来访者说话后，判断应该转接哪个部门。

### 2.3 session.get_agent_state(target) — 获取Agent局部状态

**作用**：获取目标Agent的"专属记忆"。

**为什么需要？** 一个session中用户可能跟多个Agent交互：
- 先问了数据（query_agent有自己的历史）
- 再设计套餐（design_agent有自己的历史）
- 两者互不污染

```python
# Session内部结构：
session.agent_states = {
    "query_agent": AgentState(history=[...], context={...}),
    "design_agent": AgentState(history=[...], context={...}),
    "config_agent": AgentState(history=[...], context={...}, step="tariff"),
}
```

每个AgentState只记录与该Agent相关的对话和数据。

### 2.4 _prepare_agent_input() — 上下文裁剪

**作用**：为子Agent精心准备输入，而不是粗暴地把全部历史塞给它。

**组装逻辑**（按顺序）：
```
1. shared_context    → 其他Agent的关键结果（如问数结果"月均15.2GB"）
2. agent历史[-6:]   → 该Agent自己最近6轮对话（保持连贯性）
3. context_summary  → Supervisor提炼的本次意图摘要
4. 当前用户消息     → 用户这次说了什么
```

**为什么不直接传全部历史？**
- 省token：全部历史可能几十轮，大部分无关
- 减噪音：问数的SQL细节对设计Agent无用
- 精准：Supervisor提炼过的摘要比原始历史更有效

**类比**：老板给部门下达任务时，不会把所有会议录音发过去，而是：
- 告诉你别的部门的结论（shared_context）
- 你们部门之前的工作进展（history[-6:]）
- 这次具体要做什么（context_summary + 当前消息）

### 2.5 _update_state() — 状态更新

**作用**：Agent执行完后，更新各种状态。

```python
def _update_state(self, session, target, agent_state, user_message, result, routing):
    # 1) 记录当前活跃Agent
    session.active_agent = target

    # 2) 将本轮对话存入Agent局部历史
    agent_state.history.append(Message(role="user", content=user_message))
    agent_state.history.append(Message(role="assistant", content=result.reply))

    # 3) 如果Agent返回了数据，存入shared_context供其他Agent引用
    if result.data:
        session.shared_context[f"{target}_latest"] = {
            "summary": routing.get("context_summary"),
            "data": str(result.data)[:500]
        }

    # 4) Agent的回复也存入全局历史
    session.global_history.append(Message(role="assistant", content=result.reply))
```

**关键点**：shared_context 是跨Agent协作的桥梁。比如问数Agent返回"月均15.2GB"，
这个数据存入shared_context后，设计Agent下次被调用时就能通过 _prepare_agent_input() 拿到它。

---

## 3. Agent层：`app/agents/`

### 3.1 统一接口

所有Agent继承 BaseAgent，实现同一个方法：
```python
async def execute(self, messages: list[Message], state: AgentState) -> AgentResult
```

- `messages`：Supervisor裁剪好的输入（不是全部历史）
- `state`：该Agent的局部状态（可读可写，如配置Agent更新step）
- 返回 `AgentResult`：统一的输出结构

### 3.2 问数Agent（最简单）

```
messages → LLM生成SQL → 模拟执行 → LLM解读结果 → AgentResult
```
单链路，无状态。

### 3.3 设计Agent（展示Skill模式）

```
messages → TagReasoningSkill → DesignSuggestionSkill → CaseMatchingSkill → AgentResult
                  ↓ 输出标签            ↓ 引用标签             ↓ 引用标签
              context["tag_reasoning"]传递给后续Skill
```

Skill之间通过 `context` 字典传递中间结果。流水线模式：前一个Skill的输出是后一个的输入。

### 3.4 配置Agent（展示状态机）

```
第1次调用: step=None → 填充basic_info → step="tariff"
第2次调用: step="tariff" → 填充tariff → step="rental"  
第3次调用: step="rental" → 填充rental → step="done"
```

通过 `state.step` 记录当前进度，实现多轮逐步配置。

---

## 4. Skill层：`app/agents/design_agent.py` 内部

### 4.1 Skill接口

```python
class Skill(ABC):
    name: str           # 标识符
    description: str    # 供LLM理解用途（动态编排时使用）

    async def run(self, input: SkillInput) -> SkillOutput
```

### 4.2 SkillInput — Skill的输入

```python
@dataclass
class SkillInput:
    messages: list[Message]    # 用户对话上下文
    context: dict              # 前序Skill的输出结果
```

`context` 是Skill之间的传递带：
```python
# 执行流水线时：
context = {}
# 第1个Skill执行后：context = {"tag_reasoning": [标签列表]}
# 第2个Skill可以通过 input.context["tag_reasoning"] 拿到标签
# 第3个Skill同样可以引用
```

### 4.3 固定流水线 vs LLM动态编排

当前用固定流水线（Skill少、顺序明确时）：
```python
skill_pipeline = ["tag_reasoning", "design_suggestion", "case_matching"]
for skill_name in self.skill_pipeline:
    output = await skill.run(...)
```

未来Skill变多时，可切换为LLM动态编排（让LLM决定用哪些Skill）：
```python
plan = await self.llm.plan(messages, available_skills=skill_descriptions)
for skill_name in plan.skill_sequence:
    output = await skill.run(...)
```

---

## 5. 状态流转图示

### 5.1 单次请求

```
Session (持久)
├── global_history: [user1, assistant1, user2, assistant2, ...]  ← 每轮追加
├── active_agent: "design_agent"                                 ← 每轮更新
├── shared_context: {"query_agent_latest": {"data": "15.2GB"}}  ← Agent有数据时更新
└── agent_states:
    ├── query_agent:  {history: [...], context: {}}
    ├── design_agent: {history: [...], context: {tags: [...]}}
    └── config_agent: {history: [...], context: {basic_info: {...}}, step: "tariff"}
```

### 5.2 跨Agent协作示例

```
用户: "广东5G用户月均流量"
  → Supervisor路由 → query_agent
  → 执行，返回 "15.2GB"
  → shared_context["query_agent_latest"] = "15.2GB"

用户: "基于这个数据设计套餐"
  → Supervisor路由 → design_agent
  → _prepare_agent_input() 时，把 shared_context 注入：
    "参考信息：query_agent_latest: 15.2GB"
  → design_agent 看到参考信息，设计时考虑15.2GB这个数据
```

---

## 6. 调试建议

在 PyCharm 中打断点的推荐位置：

| 文件 | 行 | 观察什么 |
|------|-----|---------|
| `api/chat.py` | `result = await supervisor.handle(...)` | 请求入口 |
| `supervisor.py` | `routing = await self._route(...)` | 看路由决策JSON |
| `supervisor.py` | `agent_messages = self._prepare_agent_input(...)` | 看裁剪后的上下文 |
| `supervisor.py` | `result = await agent.execute(...)` | 看Agent输出 |
| `supervisor.py` | `self._update_state(...)` | 看状态如何更新 |
| `design_agent.py` | `output = await skill.run(...)` | 看Skill流水线 |
| `config_agent.py` | `state.step = next_step` | 看状态机推进 |

---

## 7. 核心设计原则

1. **分层解耦**：Supervisor不关心Agent内部实现，Agent不关心Skill细节
2. **状态外置**：Agent本身无状态，状态由Session管理并注入，方便测试和重放
3. **上下文裁剪**：每层只看到自己需要的信息，避免信息过载
4. **统一接口**：AgentResult统一了所有Agent的输出格式，方便前端渲染
5. **递归模式**：Supervisor选Agent、Agent选Skill，每层的模式相同（识别→选择→执行→组合）
