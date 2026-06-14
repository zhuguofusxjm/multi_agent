# 运营商统一智能体平台 — 架构设计

## 1. 背景与目标

### 现状
现有3个独立的COT智能体（问数、套餐设计、套餐配置），各自独立入口，不支持多轮会话，无法跨Agent协作。

### 目标
- 统一入口：单一输入框，类似Gemini体验
- 多轮会话：支持对结果的局部调整和追问
- 跨Agent协作：一次会话中多个Agent可穿插使用，上下文自然衔接
- 可扩展：子Agent内部可拆分为多个Skill，复杂度可控

### 约束
- 技术栈：Python + FastAPI
- LLM：DeepSeek API（环境变量 DEEPSEEK_API_KEY）
- 范围：本次聚焦后端架构，前端待定
- 会话持久化：待定，架构预留接口

---

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Server                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  用户消息 ──→ SessionManager ──→ Supervisor Agent           │
│                 (会话状态)         (意图路由+上下文裁剪)       │
│                                       │                     │
│                          ┌────────────┼────────────┐        │
│                          ▼            ▼            ▼        │
│                     问数Agent    设计Agent    配置Agent      │
│                     (SQL生成)   (标签推理)   (配置填充)       │
│                          │            │            │        │
│                          └────────────┼────────────┘        │
│                                       ▼                     │
│                              Supervisor 整合回复             │
│                                       │                     │
│                                       ▼                     │
│                              响应返回给用户                   │
└─────────────────────────────────────────────────────────────┘
```

三层结构：Supervisor → Agent → Skill

- **Supervisor**：意图识别、路由决策、上下文裁剪、结果整合
- **Agent**：领域专家，处理特定类型任务
- **Skill**：Agent内部的原子能力单元（扩展时使用）

---

## 3. 核心组件设计

### 3.1 SessionManager（会话状态管理）

```python
@dataclass
class AgentState:
    """单个子Agent的局部状态"""
    name: str
    history: list[Message]
    context: dict
    step: str | None = None

@dataclass
class Session:
    """一次用户会话的完整状态"""
    session_id: str
    global_history: list[Message]
    active_agent: str | None
    agent_states: dict[str, AgentState]
    shared_context: dict
```

关键设计决策：
- `global_history`：完整对话记录，供Supervisor做路由决策
- `agent_states`：各子Agent独立状态，互不污染
- `shared_context`：跨Agent共享的关键信息（如问数结果供设计Agent引用）
- `step`：多步骤Agent（如配置Agent）的进度追踪

### 3.2 Supervisor Agent

职责：
1. 接收用户消息 + global_history
2. 判断目标Agent + 是否为追问
3. 裁剪上下文，为目标Agent准备输入
4. 整合Agent结果，提取关键信息存入shared_context

路由输出格式：
```json
{
  "target_agent": "query_agent|design_agent|config_agent",
  "is_followup": true,
  "context_summary": "传递给子Agent的关键上下文摘要"
}
```

上下文裁剪策略：
- 子Agent自身历史（最近6轮）
- shared_context中的相关信息
- Supervisor提炼的上下文摘要
- 当前用户消息

兜底策略：
- 无法识别意图时，Supervisor直接作为通用对话Agent回复，并引导用户明确需求
- 意图模糊时（如可能是问数也可能是设计），Supervisor追问一次澄清

### 3.3 子Agent设计

#### 问数Agent（QueryAgent）
- 输入：用户自然语言问题
- 流程：LLM生成SQL → 安全校验 → 执行 → LLM解读结果
- 输出：自然语言回答 + 原始数据

#### 设计Agent（DesignAgent）
- 输入：套餐设计需求
- 流程：LLM推理Top10标签+原因 → LLM补充设计建议 → 标签检索案例库
- 输出：设计建议（主面板）+ 匹配案例（侧面板）

#### 配置Agent（ConfigAgent）
- 输入：配置需求
- 流程：按步骤（basic_info → tariff → rental）逐步由LLM填充
- 输出：配置结果（主面板）+ 配置树（侧面板）
- 特殊：有明确的步骤状态机

### 3.4 统一返回结构

```python
@dataclass
class AgentResult:
    reply: str              # 主聊天区文本
    side_panel: Any = None  # 右侧面板内容（案例/配置树/图表）
    data: Any = None        # 原始数据（供跨Agent引用）
    metadata: dict = None   # 元信息（如SQL、标签等）
```

---

## 4. Skill 扩展机制

当子Agent变复杂后，内部拆分为多个Skill。以**设计Agent**为例展示完整模式：

### 4.1 Skill 基类

```python
@dataclass
class SkillInput:
    messages: list[Message]     # 当前上下文
    context: dict               # 前序Skill的输出可作为后续输入

@dataclass
class SkillOutput:
    result: Any                 # 该Skill的输出数据
    summary: str                # 简短描述，供后续Skill/LLM理解

class Skill(ABC):
    name: str
    description: str            # 供LLM理解该Skill的用途，用于动态编排

    @abstractmethod
    async def run(self, input: SkillInput) -> SkillOutput:
        ...
```

### 4.2 设计Agent的Skill拆分示例

```python
class TagReasoningSkill(Skill):
    """从需求中推理出最匹配的Top10标签"""
    name = "tag_reasoning"
    description = "根据套餐设计需求，从标签库中推理最匹配的Top10标签并给出理由"

    async def run(self, input: SkillInput) -> SkillOutput:
        prompt = f"标签库：{self.tag_library}\n需求：{input.messages[-1].content}"
        tags = await self.llm.call(prompt)
        return SkillOutput(result=tags, summary=f"推荐标签：{tags[:3]}...")


class DesignSuggestionSkill(Skill):
    """基于标签发散补充设计建议"""
    name = "design_suggestion"
    description = "基于已选标签，补充价格策略、差异化卖点、目标人群等设计建议"

    async def run(self, input: SkillInput) -> SkillOutput:
        tags = input.context.get("tag_reasoning")  # 引用前序Skill输出
        suggestions = await self.llm.call(f"标签：{tags}\n请补充设计建议")
        return SkillOutput(result=suggestions, summary="设计建议已生成")


class CaseMatchingSkill(Skill):
    """用标签检索最匹配的案例"""
    name = "case_matching"
    description = "根据推荐标签在案例库中检索最匹配的历史套餐案例"

    async def run(self, input: SkillInput) -> SkillOutput:
        tags = input.context.get("tag_reasoning")
        cases = await self.case_store.search(tags.result)
        return SkillOutput(result=cases, summary=f"匹配到{len(cases)}个案例")
```

### 4.3 Agent内部的Skill编排

Agent通过两种方式编排Skill：

**方式一：固定流水线（简单场景）**
```python
class DesignAgent:
    skill_pipeline = ["tag_reasoning", "design_suggestion", "case_matching"]

    async def execute(self, messages, state):
        context = {}
        for skill_name in self.skill_pipeline:
            skill = self.skills[skill_name]
            output = await skill.run(SkillInput(messages=messages, context=context))
            context[skill_name] = output.result
        return self.compose_result(context)
```

**方式二：LLM动态编排（复杂场景，Skill数量多时）**
```python
class DesignAgent:
    async def execute(self, messages, state):
        # LLM根据需求决定使用哪些Skill、什么顺序
        skill_descriptions = {s.name: s.description for s in self.skills.values()}
        plan = await self.llm.plan(messages, available_skills=skill_descriptions)

        context = {}
        for skill_name in plan.skill_sequence:
            skill = self.skills[skill_name]
            output = await skill.run(SkillInput(messages=messages, context=context))
            context[skill_name] = output.result
        return self.compose_result(context)
```

### 4.4 三层递归结构总结

```
Supervisor（路由层）
  ├── 选择 Agent（根据意图）
  │
Agent（编排层）
  ├── 选择 Skill 组合（固定流水线 或 LLM动态编排）
  │
Skill（执行层）
  └── 完成具体原子任务
```

每一层的模式相同：识别需求 → 选择执行单元 → 组合结果。Skill越多，Agent内部可以切换为LLM动态编排；Skill少时用固定流水线即可。

---

## 5. API 接口

### POST /chat

Request:
```json
{
  "session_id": "optional",
  "message": "用户输入"
}
```

Response:
```json
{
  "session_id": "abc123",
  "reply": "主聊天区文本",
  "side_panel": {
    "type": "cases|config_tree|chart",
    "data": {}
  },
  "active_agent": "design_agent",
  "metadata": {}
}
```

---

## 6. 请求处理流程

1. 用户发送消息
2. SessionManager 加载/创建 Session
3. 消息追加到 global_history
4. Supervisor LLM 调用 → 路由决策
5. prepare_agent_input() 裁剪上下文
6. 目标子Agent执行 → AgentResult
7. 关键数据存入 shared_context
8. 更新 agent_state
9. 返回响应

---

## 7. 项目结构

```
telecom-agent/
├── app/
│   ├── main.py              # FastAPI入口
│   ├── api/
│   │   └── chat.py          # /chat 接口
│   ├── core/
│   │   ├── supervisor.py    # Supervisor 路由逻辑
│   │   ├── session.py       # SessionManager + 状态定义
│   │   └── llm_client.py    # DeepSeek API 封装（兼容OpenAI SDK接口）
│   ├── agents/
│   │   ├── base.py          # Agent基类 + AgentResult + Skill基类
│   │   ├── query_agent.py   # 问数Agent
│   │   ├── design_agent.py  # 设计Agent
│   │   └── config_agent.py  # 配置Agent
│   └── data/
│       ├── table_schemas.py  # 大宽表定义
│       ├── tag_library.py    # 标签库
│       └── case_store.py     # 案例库检索
├── tests/
├── requirements.txt
└── README.md
```

---

## 8. 关键设计决策总结

| 维度 | 决策 | 理由 |
|------|------|------|
| 框架 | 原生Python + FastAPI | 深入理解原理，无黑盒依赖 |
| 路由 | Supervisor LLM自动路由 | 用户无感，体验流畅 |
| 多轮 | Session状态管理 | global_history + agent_states 分层 |
| 跨Agent | shared_context + 上下文裁剪 | 避免token浪费，信息精准传递 |
| 子Agent | 无状态设计 | 状态由外部注入，易测试易扩展 |
| 扩展 | Skill抽象层 | 三层递归结构，复杂度分层管控 |
| LLM | DeepSeek API（DEEPSEEK_API_KEY） | 已有可用key，兼容OpenAI SDK接口 |

---

## 9. 验证方案

1. 单元测试：每个Agent独立测试，mock LLM响应
2. 集成测试：模拟多轮会话场景，验证路由和状态流转
3. 端到端测试：
   - 单Agent多轮：问数后追问、设计后修改
   - 跨Agent：先问数→再设计→再配置
   - 边界：无法识别意图时的兜底处理
4. 启动FastAPI dev server，通过curl/httpie测试 /chat 接口
