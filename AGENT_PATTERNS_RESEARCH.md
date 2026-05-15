# Advanced AI Agent Patterns: Beyond Basic RAG

## Research Report & Implementation Guide

**Date:** 2026-05-14
**Sources:** LangGraph Documentation, Anthropic "Building Effective Agents", ReAct Paper (Yao et al.), Reflexion Paper (Shinn et al.), Tree of Thoughts (Yao et al.), Claude Code Best Practices

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Multi-Step Reasoning Patterns](#1-multi-step-reasoning-patterns)
3. [Tool Use with Reflection](#2-tool-use-with-reflection)
4. [Agent Architectures](#3-agent-architectures)
5. [Memory and Context Management](#4-memory-and-context-management)
6. [Claude Code-Like Behavior](#5-claude-code-like-behavior)
7. [Architecture Patterns Comparison](#6-architecture-patterns-comparison)
8. [Recommended Approach for Document Q&A](#7-recommended-approach-for-document-qa)
9. [Implementation Roadmap](#8-implementation-roadmap)
10. [Code Examples with LangGraph](#9-code-examples-with-langgraph)
11. [References](#references)

---

## Executive Summary

Basic RAG (Retrieval-Augmented Generation) answers questions by retrieving relevant document chunks and generating a response in a single pass. While effective for simple factual queries, it struggles with:

- Multi-hop reasoning (connecting information across multiple documents)
- Complex planning and task decomposition
- Self-correction when retrieval fails
- Iterative refinement of answers
- Long-term session memory and personalization

This report surveys the state-of-the-art patterns for making AI assistants more agent-like: capable of reasoning, planning, using tools, reflecting on mistakes, and managing memory. The key insight from Anthropic's research with production teams is that **the most successful implementations use simple, composable patterns rather than complex frameworks**. Start simple, add complexity only when it demonstrably improves outcomes.

---

## 1. Multi-Step Reasoning Patterns

### 1.1 Chain of Thought (CoT)

**Concept:** Prompt the model to generate intermediate reasoning steps before arriving at a final answer.

**How it works:**
- Append "Let's think step by step" or similar to prompts
- The model generates a reasoning trace followed by the answer
- Can be zero-shot (implicit in prompt) or few-shot (with examples)

**Strengths:**
- Dramatically improves performance on math, logic, and reasoning tasks
- Free-form, no architectural changes needed
- Human-interpretable reasoning traces

**Limitations:**
- Linear; no backtracking or exploration of alternatives
- Prone to hallucination in reasoning steps
- No interaction with external tools or environments

### 1.2 Tree of Thoughts (ToT)

**Concept:** Generalize CoT to a tree structure where the model can explore multiple reasoning paths, evaluate them, and backtrack.

**How it works:**
1. **Thought Generation:** Generate multiple candidate thoughts (intermediate steps)
2. **State Evaluation:** Score each thought's promise (value function)
3. **Search Algorithm:** Use breadth-first or depth-first search with pruning
4. **Backtracking:** If a path fails, return to a promising node and try alternatives

**Key Parameters:**
- `k`: Number of thoughts to generate per step
- `threshold`: Minimum score to keep exploring a branch
- `max_depth`: Maximum reasoning depth

**Strengths:**
- Solves problems requiring exploration and planning
- Self-evaluation prevents following dead-end reasoning paths
- Achieved 74% on Game of 24 (vs 4% for CoT)

**Limitations:**
- Higher token cost (generates multiple candidates)
- More complex to implement
- Best for hard problems where initial decisions matter

### 1.3 Plan-and-Execute

**Concept:** Separate planning from execution into distinct phases.

**How it works:**
1. **Planning Phase:** LLM generates a step-by-step plan to accomplish the task
2. **Execution Phase:** Each step is executed (often by tools or sub-agents)
3. **Replanning:** If execution fails or new information emerges, replan

**Strengths:**
- Clear separation of concerns
- Plans are inspectable and modifiable by humans
- Can use cheaper/faster models for execution, powerful models for planning
- Natural fit for document analysis workflows

**Limitations:**
- Plans may become outdated during execution
- Overhead of planning before doing
- Rigid if the environment changes unexpectedly

### 1.4 Prompt Chaining

**Concept:** Decompose a task into a sequence of LLM calls, where each call processes the output of the previous one.

**How it works:**
```
Input -> LLM Step 1 -> [Gate/Check] -> LLM Step 2 -> ... -> Output
```

**Strengths:**
- Simple to implement and debug
- Each step is an easier task for the LLM
- Can add programmatic checks between steps
- Ideal for fixed workflows (outline -> draft -> edit)

**Limitations:**
- Fixed sequence; not adaptive
- Latency adds up with each LLM call
- Error propagation if an early step is wrong

---

## 2. Tool Use with Reflection

### 2.1 Structured Tool Calling

Modern LLMs (Claude, GPT-4, Gemini) support native function/tool calling:

```python
# Tool definition with Pydantic schema
class SearchInput(BaseModel):
    query: str = Field(description="Search query string")
    filters: dict = Field(default={}, description="Optional metadata filters")

@tool(args_schema=SearchInput)
def search_documents(query: str, filters: dict = {}) -> str:
    """Search the document knowledge base."""
    results = vector_store.similarity_search(query, filter=filters)
    return format_results(results)
```

**Best Practices for Tool Design (from Anthropic):**
1. **Put yourself in the model's shoes** - Is it obvious how to use the tool?
2. **Invest in Agent-Computer Interface (ACI)** - As much effort as HCI
3. **Include example usage** in tool descriptions
4. **Poka-yoke (mistake-proof) your tools** - Use absolute paths, clear enums
5. **Keep formats close to what the model saw in training** - Markdown over JSON for code
6. **Give the model enough tokens to "think"** before writing itself into a corner

### 2.2 Self-Correction and Retry Logic

**Concept:** The agent evaluates tool outputs and decides whether to retry with different parameters.

**Implementation Pattern:**
```python
async def execute_with_retry(tool_call, max_retries=3):
    for attempt in range(max_retries):
        result = await execute_tool(tool_call)
        
        # Self-evaluation
        evaluation = await llm.ainvoke(
            f"Tool result: {result}\nIs this sufficient to answer the query?"
        )
        
        if evaluation.is_sufficient:
            return result
        
        # Generate improved tool call
        tool_call = await llm.ainvoke(
            f"Previous attempt failed. Result: {result}\nGenerate better parameters."
        )
    
    return "Failed after maximum retries"
```

**Strategies for Retry:**
1. **Parameter refinement:** Adjust search queries, filters, or thresholds
2. **Tool substitution:** Try a different tool if the current one fails
3. **Decomposition:** Break a failed tool call into smaller sub-calls
4. **Fallback:** Return a partial answer or "I don't know"

### 2.3 Tool Selection with Reasoning

**Concept:** Before calling a tool, the agent explicitly reasons about which tool to use and how.

**Pattern:**
```
User Query -> Reasoning ("I need to search for X, then calculate Y") 
-> Tool Selection -> Tool Execution -> Observation -> ...
```

This is the core of the ReAct pattern (see Section 3).

---

## 3. Agent Architectures

### 3.1 ReAct (Reasoning + Acting)

**Source:** Yao et al., "ReAct: Synergizing Reasoning and Acting in Language Models" (ICLR 2023)

**Concept:** Interleave reasoning traces (Thought) with actions (Act) and observations from the environment.

**Pattern:**
```
Thought 1: I need to find the revenue for Q3 2024.
Act 1: search_documents(query="Q3 2024 revenue")
Obs 1: [Returns document about Q3 earnings call]
Thought 2: This mentions revenue but not the exact number. Let me search more specifically.
Act 2: search_documents(query="revenue figures third quarter 2024")
Obs 2: [Returns financial table]
Thought 3: I found the revenue is $50M. I can now answer the question.
Act 3: finish(answer="The Q3 2024 revenue was $50 million.")
```

**Strengths:**
- Reasoning traces help track and update plans
- Actions gather external information to ground reasoning
- More interpretable and trustworthy than act-only agents
- Overcomes hallucination by grounding in tool outputs

**Implementation in LangGraph:**
```python
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()
agent = create_react_agent(llm, tools, checkpointer=checkpointer)
```

**When to use:**
- Question answering with multiple retrieval steps
- Tasks requiring reasoning about external data
- When interpretability is important

### 3.2 Plan-and-Execute Agents

**Concept:** A planner generates a high-level plan, then an executor carries out each step.

**LangGraph Implementation:**
```python
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated

class PlanExecuteState(TypedDict):
    input: str
    plan: list[str]
    past_steps: Annotated[list[tuple], "executed steps with results"]
    response: str

async def planner(state: PlanExecuteState):
    """Generate plan based on input."""
    plan = await llm.ainvoke(f"Create a plan to: {state['input']}")
    return {"plan": plan.steps}

async def executor(state: PlanExecuteState):
    """Execute the next step in the plan."""
    current_step = state["plan"][len(state["past_steps"])]
    result = await execute_step(current_step)
    return {"past_steps": [(current_step, result)]}

async def replanner(state: PlanExecuteState):
    """Decide whether to continue or finish."""
    if len(state["past_steps"]) >= len(state["plan"]):
        response = await synthesize_answer(state)
        return {"response": response}
    
    # Check if plan needs updating
    new_plan = await llm.ainvoke(
        f"Original plan: {state['plan']}\nResults so far: {state['past_steps']}\nUpdate plan if needed."
    )
    return {"plan": new_plan.steps}

# Build graph
builder = StateGraph(PlanExecuteState)
builder.add_node("planner", planner)
builder.add_node("executor", executor)
builder.add_node("replanner", replanner)

builder.add_edge(START, "planner")
builder.add_edge("planner", "executor")
builder.add_edge("executor", "replanner")
builder.add_conditional_edges("replanner", should_continue, {
    "continue": "executor",
    "end": END
})
```

**Strengths:**
- Plans are human-inspectable and editable
- Can pause for human approval at any step
- Natural fit for document analysis pipelines
- Planner can use powerful model, executor can use faster model

**When to use:**
- Multi-step document analysis
- Workflows with clear sequential steps
- When human oversight is needed

### 3.3 Reflexion (Self-Reflective Agents)

**Source:** Shinn et al., "Reflexion: Language Agents with Verbal Reinforcement Learning" (2023)

**Concept:** Agent verbally reflects on task feedback, maintains reflective text in episodic memory, and uses it to improve future decisions.

**Core Loop:**
```
1. Attempt task -> Get result
2. Evaluate result (external or internal feedback)
3. Generate reflection: "I should have searched for X before Y"
4. Store reflection in memory buffer
5. On next attempt, include relevant reflections in context
```

**Types of Feedback:**
- **Scalar:** Success/failure scores
- **Free-form:** Verbal critique of what went wrong
- **External:** Unit tests, compilation errors, human feedback
- **Internal:** Self-evaluation by the LLM

**Implementation Pattern:**
```python
class ReflexionState(TypedDict):
    query: str
    attempts: list[dict]  # Each attempt with result and reflection
    current_attempt: int
    max_attempts: int
    reflections: list[str]  # Accumulated learnings

async def attempt_task(state: ReflexionState):
    # Include past reflections in prompt
    context = "\n".join(state["reflections"])
    result = await agent_with_tools.ainvoke(
        f"Task: {state['query']}\nPast learnings: {context}"
    )
    return {"attempts": [{"result": result, "reflection": None}]}

async def reflect(state: ReflexionState):
    last_attempt = state["attempts"][-1]
    reflection = await llm.ainvoke(
        f"Your previous answer was: {last_attempt['result']}\n"
        f"Evaluate what went wrong and how to improve."
    )
    return {
        "reflections": [reflection],
        "attempts": [{**last_attempt, "reflection": reflection}]
    }

async def decide(state: ReflexionState):
    if state["current_attempt"] >= state["max_attempts"]:
        return "finish"
    evaluation = await llm.ainvoke(
        f"Is this answer good enough? {state['attempts'][-1]['result']}"
    )
    return "finish" if evaluation.is_good else "retry"
```

**Strengths:**
- Learns from mistakes without model fine-tuning
- Reflections are human-interpretable
- Flexible with different feedback types
- Achieved 91% on HumanEval (vs 80% for GPT-4)

**When to use:**
- Coding tasks with test feedback
- Iterative document analysis
- Any task with verifiable outcomes

### 3.4 Multi-Agent Systems

**Concept:** Multiple specialized agents collaborate, supervised by an orchestrator.

**Patterns:**

**A. Supervisor Pattern:**
```
User Query -> Supervisor (routes to specialist)
-> Researcher / Writer / Coder / Reviewer
-> Supervisor synthesizes -> Answer
```

**B. Orchestrator-Workers:**
```
Orchestrator breaks task into subtasks -> Workers execute in parallel
-> Orchestrator synthesizes results -> Answer
```

**C. Debate/Ensemble:**
```
Query -> Multiple agents generate answers independently
-> Aggregator/voting selects best answer
```

**When to use:**
- Complex tasks spanning multiple domains
- When quality matters more than latency
- Code generation with separate review agent

---

## 4. Memory and Context Management

### 4.1 Session Memory (Short-Term)

**Concept:** Maintain conversation history within a single session.

**LangGraph Implementation:**
```python
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()
agent = create_react_agent(llm, tools, checkpointer=checkpointer)

# Thread ID isolates conversations
config = {"configurable": {"thread_id": "session-abc123"}}
result = await agent.ainvoke({"messages": [...]}, config)
```

**Types:**
- **Buffer Memory:** Store all messages (good for short conversations)
- **Summary Memory:** Summarize older turns (good for long conversations)
- **Token Buffer:** Window based on token count

### 4.2 Long-Term Knowledge

**Concept:** Persist information across sessions using vector stores.

**Implementation:**
```python
from langchain_community.vectorstores import Chroma

memory_store = Chroma(
    collection_name="conversation_memory",
    embedding_function=embeddings,
    persist_directory="./memory_db"
)

async def store_fact(user_id: str, fact: str):
    await memory_store.aadd_texts(
        [fact],
        metadatas=[{"user_id": user_id, "type": "preference"}]
    )

async def recall_facts(user_id: str, query: str, k: int = 5):
    docs = await memory_store.asimilarity_search(
        query,
        k=k,
        filter={"user_id": user_id}
    )
    return [doc.page_content for doc in docs]
```

### 4.3 Context Compression

**Problem:** LLM context windows fill up, degrading performance.

**Solutions:**

**A. Summarization:**
```python
async def compress_messages(messages: list, max_tokens: int = 4000):
    if estimate_tokens(messages) < max_tokens:
        return messages
    
    # Summarize oldest messages
    old_messages = messages[:-10]
    recent_messages = messages[-10:]
    
    summary = await llm.ainvoke(
        f"Summarize these messages concisely: {old_messages}"
    )
    
    return [SystemMessage(content=summary)] + recent_messages
```

**B. Selective Loading:**
- Only load relevant documents (RAG)
- Filter conversation by relevance to current query
- Use message importance scoring

**C. Claude Code Approach:**
- `/clear` between unrelated tasks
- `/compact` to summarize mid-conversation
- Subagents for investigation (keep main context clean)
- Skills for domain knowledge (load on demand)

### 4.4 Episodic vs Semantic Memory

| Type | Content | Retrieval | Use Case |
|------|---------|-----------|----------|
| **Episodic** | Past conversation turns | Recency + relevance | Session continuity |
| **Semantic** | Facts, preferences, rules | Similarity search | Personalization |
| **Procedural** | How to do things (skills) | Name/keyword | Task execution |

---

## 5. Claude Code-Like Behavior

### 5.1 Core Principles

Claude Code demonstrates effective agentic behavior through:

1. **Explore First, Then Plan, Then Code**
   - Plan mode: Read files and answer questions without making changes
   - Planning: Create detailed implementation plans
   - Implementation: Execute with verification

2. **Provide Verification Criteria**
   - Tests, screenshots, expected outputs
   - Self-verification dramatically improves accuracy
   - Agent checks its own work

3. **Aggressive Context Management**
   - Context window is the fundamental constraint
   - `/clear` between unrelated tasks
   - Subagents for investigation (isolated context)
   - Compact/summarize when approaching limits

4. **Iterative Refinement**
   - Course-correct early and often
   - After two failed corrections, restart with better prompt
   - Checkpoints allow rewinding to previous states

### 5.2 Applying to Document Q&A

For a document Q&A app, Claude Code patterns translate to:

**Explore Phase:**
- Analyze document structure and content types
- Identify key sections, tables, and relationships
- Build a mental model of the document

**Plan Phase:**
- For complex queries, generate a retrieval plan
- "First search for revenue data, then cross-reference with quarterly reports"

**Implement Phase:**
- Execute retrievals according to plan
- Verify answer against source documents
- Cite specific locations

**Verify Phase:**
- Check if answer is fully supported by retrieved context
- Identify gaps requiring additional retrieval
- Retry with refined queries if needed

### 5.3 Task Decomposition

**Simple Decomposition:**
```
"Compare Q3 and Q4 revenue"
-> 1. Retrieve Q3 revenue
-> 2. Retrieve Q4 revenue  
-> 3. Compare and generate answer
```

**Complex Decomposition (Orchestrator-Workers):**
```
"Analyze the company's financial health"
-> Orchestrator creates subtasks:
  - Worker 1: Analyze revenue trends
  - Worker 2: Analyze debt and liabilities
  - Worker 3: Analyze cash flow
-> Orchestrator synthesizes findings
```

---

## 6. Architecture Patterns Comparison

| Pattern | Complexity | Latency | Cost | Adaptability | Best For |
|---------|-----------|---------|------|--------------|----------|
| **Basic RAG** | Low | Low | Low | None | Simple factual Q&A |
| **Prompt Chaining** | Low | Medium | Medium | Low | Fixed workflows |
| **ReAct** | Medium | Medium | Medium | High | Multi-step reasoning |
| **Plan-and-Execute** | Medium | Medium | Medium | Medium | Structured tasks |
| **Reflexion** | High | High | High | High | Iterative improvement |
| **Tree of Thoughts** | High | High | Very High | Very High | Complex problem solving |
| **Multi-Agent** | High | High | High | High | Multi-domain tasks |

### When to Use What

**Start with:** Basic RAG + ReAct for retrieval
**Add when needed:**
- Plan-and-Execute: For multi-document analysis pipelines
- Reflexion: When answers need to be verified and improved
- ToT: For complex reasoning requiring exploration
- Multi-Agent: When task spans multiple expertise areas

**Anthropic's Recommendation:**
> "Start with simple prompts, optimize them with comprehensive evaluation, and add multi-step agentic systems only when simpler solutions fall short."

---

## 7. Recommended Approach for Document Q&A

### 7.1 Tiered Architecture

We recommend a **tiered approach** where complexity increases based on query characteristics:

```
User Query
    |
    v
[Classifier] -> Simple? -> [Basic RAG] -> Answer
    |
    v
Complex? -> [Plan-and-Execute with ReAct]
    |
    +-- Plan: Decompose into retrieval steps
    +-- Execute: ReAct agent performs retrievals
    +-- Verify: Check answer completeness
    +-- Refine: Retry if gaps found
    |
    v
Answer with citations
```

### 7.2 Specific Recommendations

**Phase 1: Enhanced RAG (Immediate)**
- Agentic retrieval: LLM generates search queries dynamically
- Multi-step retrieval: Follow-up searches based on initial findings
- Source attribution: Every claim linked to document location

**Phase 2: Plan-and-Execute (Short-term)**
- Query planner analyzes question complexity
- Generates retrieval strategy
- Executes with ReAct agent
- Replan if initial retrieval insufficient

**Phase 3: Reflection & Memory (Medium-term)**
- Evaluate answer quality against retrieved context
- Store successful retrieval patterns as semantic memory
- Learn user preferences (preferred detail level, format)
- Compress and summarize long conversations

**Phase 4: Advanced Features (Long-term)**
- Multi-document comparison with orchestrator-workers
- Cross-document reasoning ("Compare this report with last quarter's")
- Proactive suggestions based on document content

### 7.3 Document Q&A Specific Patterns

**Pattern: Multi-Hop Retrieval**
```
Query: "What was the revenue impact of the acquisition mentioned in the CEO letter?"
Step 1: Retrieve CEO letter, find acquisition name
Step 2: Retrieve financial section for acquisition revenue impact
Step 3: Synthesize answer with both sources
```

**Pattern: Structured Data Extraction**
```
Query: "List all contracts expiring in Q2 2025"
Step 1: Retrieve relevant sections
Step 2: Extract structured data (entity, date, value)
Step 3: Filter by date range
Step 4: Format as table
```

**Pattern: Comparative Analysis**
```
Query: "How did the strategy change from 2023 to 2024?"
Step 1: Retrieve 2023 strategy document
Step 2: Retrieve 2024 strategy document
Step 3: Identify key differences
Step 4: Analyze implications
```

---

## 8. Implementation Roadmap

### Week 1-2: Foundation

**Goal:** Enhanced RAG with basic agentic retrieval

**Tasks:**
1. Implement ReAct agent with retrieval tool
2. Add dynamic query generation (LLM crafts search queries)
3. Add source attribution to all answers
4. Implement conversation memory with LangGraph checkpointer

**Success Criteria:**
- Agent can perform 2+ retrieval steps for complex queries
- All answers include document citations
- Session memory works across multiple turns

### Week 3-4: Planning Layer

**Goal:** Plan-and-Execute for complex queries

**Tasks:**
1. Implement query complexity classifier
2. Build planner node (generates retrieval strategy)
3. Build executor node (ReAct agent with retrieval tools)
4. Add replanning logic when retrieval fails

**Success Criteria:**
- Complex queries automatically get planned
- Plans are visible to users
- System replans when information is missing

### Week 5-6: Reflection & Quality

**Goal:** Self-evaluation and iterative improvement

**Tasks:**
1. Implement answer grader (evaluates completeness)
2. Add reflection node for failed retrievals
3. Implement retry with refined queries
4. Add human feedback loop

**Success Criteria:**
- System detects when answer is incomplete
- Automatically retries with better queries
- Human feedback improves future performance

### Week 7-8: Memory & Personalization

**Goal:** Long-term memory and user adaptation

**Tasks:**
1. Implement semantic memory (vector store)
2. Store user preferences and common queries
3. Add context compression for long sessions
4. Implement skill system for common tasks

**Success Criteria:**
- System remembers user preferences across sessions
- Long sessions don't degrade in quality
- Common tasks are faster via learned patterns

---

## 9. Code Examples with LangGraph

### 9.1 Enhanced RAG Agent (ReAct Pattern)

```python
from typing import Annotated, TypedDict
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_chroma import Chroma

# Setup
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
vector_store = Chroma(...)  # Your existing vector store

# Retrieval tool with rich metadata
@tool(response_format="content_and_artifact")
def retrieve_documents(query: str, section: str = None) -> tuple[str, list]:
    """Search the document knowledge base for relevant information.
    
    Args:
        query: Search query string
        section: Optional document section filter (e.g., 'financial', 'legal')
    """
    filters = {"section": section} if section else None
    docs = vector_store.similarity_search(query, k=4, filter=filters)
    
    serialized = "\n\n".join(
        f"Source: {doc.metadata.get('source', 'unknown')}"
        f"Page: {doc.metadata.get('page', 'N/A')}\n"
        f"Content: {doc.page_content}"
        for doc in docs
    )
    return serialized, docs

# Create agent with memory
checkpointer = MemorySaver()
agent = create_react_agent(
    llm,
    [retrieve_documents],
    checkpointer=checkpointer,
    system_prompt="""You are a document analysis assistant. 
    Use the retrieve_documents tool to find information.
    Always cite your sources with document name and page number.
    If you cannot find sufficient information, say so clearly."""
)

# Use with session isolation
async def ask_question(session_id: str, question: str):
    config = {"configurable": {"thread_id": session_id}}
    result = await agent.ainvoke(
        {"messages": [("user", question)]},
        config=config
    )
    return result["messages"][-1].content
```

### 9.2 Plan-and-Execute for Document Analysis

```python
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Literal
import json

class DocumentAnalysisState(TypedDict):
    query: str
    plan: list[str]
    past_steps: Annotated[list[tuple], "executed steps with results"]
    documents: Annotated[list[dict], "retrieved documents"]
    answer: str
    needs_replan: bool

async def planner(state: DocumentAnalysisState):
    """Generate retrieval and analysis plan."""
    prompt = f"""Create a step-by-step plan to answer this document query.
    Each step should be a single retrieval or analysis action.
    
    Query: {state['query']}
    
    Respond as a JSON list of steps."""
    
    response = await llm.ainvoke(prompt)
    plan = json.loads(response.content)
    return {"plan": plan, "needs_replan": False}

async def executor(state: DocumentAnalysisState):
    """Execute the next planned step."""
    step_index = len(state["past_steps"])
    if step_index >= len(state["plan"]):
        return {"needs_replan": True}
    
    step = state["plan"][step_index]
    
    # Execute retrieval or analysis
    if "retrieve" in step.lower() or "search" in step.lower():
        result = await retrieve_documents.ainvoke({"query": step})
    else:
        result = await llm.ainvoke(f"Perform this analysis: {step}")
    
    return {
        "past_steps": [(step, result)],
        "documents": [doc for doc in result] if isinstance(result, list) else []
    }

async def evaluator(state: DocumentAnalysisState):
    """Evaluate if we have enough information."""
    prompt = f"""Query: {state['query']}
    Steps completed: {state['past_steps']}
    
    Do we have enough information to answer? Respond with:
    - "continue" if more steps needed
    - "replan" if current plan isn't working
    - "answer" if ready to synthesize answer"""
    
    response = await llm.ainvoke(prompt)
    decision = response.content.strip().lower()
    
    if "answer" in decision:
        answer = await synthesize_answer(state)
        return {"answer": answer, "needs_replan": False}
    
    return {"needs_replan": "replan" in decision}

async def synthesize_answer(state: DocumentAnalysisState):
    """Generate final answer from collected information."""
    context = "\n\n".join(
        f"Step: {step}\nResult: {result}"
        for step, result in state["past_steps"]
    )
    
    prompt = f"""Synthesize a complete answer to: {state['query']}
    
    Based on this research:
    {context}
    
    Include specific citations to source documents."""
    
    response = await llm.ainvoke(prompt)
    return response.content

def route(state: DocumentAnalysisState) -> Literal["executor", "planner", "end"]:
    if state.get("answer"):
        return "end"
    if state.get("needs_replan"):
        return "planner"
    return "executor"

# Build graph
builder = StateGraph(DocumentAnalysisState)
builder.add_node("planner", planner)
builder.add_node("executor", executor)
builder.add_node("evaluator", evaluator)

builder.add_edge(START, "planner")
builder.add_edge("planner", "executor")
builder.add_edge("executor", "evaluator")
builder.add_conditional_edges("evaluator", route, {
    "executor": "executor",
    "planner": "planner",
    "end": END
})

analysis_agent = builder.compile()
```

### 9.3 Reflection and Self-Correction Loop

```python
from langgraph.graph import StateGraph, START, END

class ReflectionState(TypedDict):
    query: str
    answer: str
    retrieved_docs: list[dict]
    reflection: str
    is_satisfactory: bool
    attempt_count: int
    max_attempts: int

async def retrieve_and_answer(state: ReflectionState):
    """Initial retrieval and answer generation."""
    docs = await retrieve_documents.ainvoke({"query": state["query"]})
    
    prompt = f"""Answer this query based on the retrieved documents.
    Query: {state['query']}
    Documents: {docs}
    
    If documents don't contain enough information, say "INSUFFICIENT"."""
    
    response = await llm.ainvoke(prompt)
    return {
        "answer": response.content,
        "retrieved_docs": docs,
        "attempt_count": state["attempt_count"] + 1
    }

async def reflect(state: ReflectionState):
    """Evaluate answer quality and generate reflection."""
    prompt = f"""Evaluate this answer critically:
    
    Query: {state['query']}
    Answer: {state['answer']}
    Sources: {state['retrieved_docs']}
    
    Check for:
    1. Factual accuracy (supported by sources?)
    2. Completeness (all aspects of query addressed?)
    3. Hallucinations (claims without source support?)
    4. Clarity and conciseness
    
    If the answer is good, respond "SATISFACTORY".
    Otherwise, provide specific feedback on what needs improvement."""
    
    response = await llm.ainvoke(prompt)
    content = response.content.strip()
    
    is_good = "SATISFACTORY" in content
    reflection = "" if is_good else content
    
    return {
        "is_satisfactory": is_good,
        "reflection": reflection
    }

def should_continue(state: ReflectionState) -> Literal["retry", "finish"]:
    if state["is_satisfactory"]:
        return "finish"
    if state["attempt_count"] >= state["max_attempts"]:
        return "finish"
    return "retry"

async def refine_query(state: ReflectionState):
    """Generate improved query based on reflection."""
    prompt = f"""Original query: {state['query']}
    Previous reflection: {state['reflection']}
    
    Generate a better search query or approach to find missing information."""
    
    response = await llm.ainvoke(prompt)
    return {"query": response.content}

# Build graph
builder = StateGraph(ReflectionState)
builder.add_node("retrieve_and_answer", retrieve_and_answer)
builder.add_node("reflect", reflect)
builder.add_node("refine_query", refine_query)

builder.add_edge(START, "retrieve_and_answer")
builder.add_edge("retrieve_and_answer", "reflect")
builder.add_conditional_edges("reflect", should_continue, {
    "retry": "refine_query",
    "finish": END
})
builder.add_edge("refine_query", "retrieve_and_answer")

self_correcting_agent = builder.compile()
```

### 9.4 Context Compression for Long Sessions

```python
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

async def compress_conversation(messages: list, max_messages: int = 20):
    """Compress conversation history while preserving key information."""
    if len(messages) <= max_messages:
        return messages
    
    # Keep system message and recent messages
    system_msgs = [m for m in messages if isinstance(m, SystemMessage)]
    recent_msgs = messages[-max_messages//2:]
    
    # Summarize middle messages
    middle_msgs = messages[len(system_msgs):-len(recent_msgs)]
    
    if middle_msgs:
        summary_prompt = f"""Summarize the key information from this conversation
        that would be needed to continue helping the user. Be concise.
        
        Conversation: {middle_msgs}"""
        
        summary = await llm.ainvoke(summary_prompt)
        summary_msg = SystemMessage(
            content=f"Previous conversation summary: {summary.content}"
        )
        return system_msgs + [summary_msg] + recent_msgs
    
    return system_msgs + recent_msgs
```

### 9.5 Multi-Agent Document Analysis

```python
from langgraph.graph import StateGraph, START, END
from typing import Literal

class MultiAgentState(TypedDict):
    query: str
    research_findings: str
    analysis: str
    draft_answer: str
    final_answer: str
    next_step: str

# Specialized agents
researcher = create_react_agent(
    llm, 
    [retrieve_documents],
    system_prompt="You are a research specialist. Find all relevant document sections."
)

analyst = create_react_agent(
    llm,
    [],
    system_prompt="You are an analyst. Synthesize findings into key insights."
)

writer = create_react_agent(
    llm,
    [],
    system_prompt="You are a writer. Create clear, well-cited answers."
)

reviewer = create_react_agent(
    llm,
    [],
    system_prompt="You are a reviewer. Check for accuracy and completeness."
)

async def supervisor(state: MultiAgentState):
    """Route to appropriate specialist."""
    if not state.get("research_findings"):
        return {"next_step": "research"}
    elif not state.get("analysis"):
        return {"next_step": "analyze"}
    elif not state.get("draft_answer"):
        return {"next_step": "write"}
    elif not state.get("final_answer"):
        return {"next_step": "review"}
    return {"next_step": "finish"}

async def do_research(state: MultiAgentState):
    result = await researcher.ainvoke({
        "messages": [("user", f"Research this thoroughly: {state['query']}")]
    })
    return {"research_findings": result["messages"][-1].content}

async def do_analysis(state: MultiAgentState):
    result = await analyst.ainvoke({
        "messages": [("user", f"Analyze these findings: {state['research_findings']}")]
    })
    return {"analysis": result["messages"][-1].content}

async def do_writing(state: MultiAgentState):
    result = await writer.ainvoke({
        "messages": [("user", f"Write an answer based on: {state['analysis']}")]
    })
    return {"draft_answer": result["messages"][-1].content}

async def do_review(state: MultiAgentState):
    result = await reviewer.ainvoke({
        "messages": [("user", f"Review this answer: {state['draft_answer']}")]
    })
    return {"final_answer": result["messages"][-1].content}

def route(state: MultiAgentState) -> Literal["research", "analyze", "write", "review", "end"]:
    return state["next_step"] if state["next_step"] != "finish" else "end"

# Build graph
builder = StateGraph(MultiAgentState)
builder.add_node("supervisor", supervisor)
builder.add_node("research", do_research)
builder.add_node("analyze", do_analysis)
builder.add_node("write", do_writing)
builder.add_node("review", do_review)

builder.add_edge(START, "supervisor")
builder.add_conditional_edges("supervisor", route, {
    "research": "research",
    "analyze": "analyze",
    "write": "write",
    "review": "review",
    "end": END
})

for node in ["research", "analyze", "write", "review"]:
    builder.add_edge(node, "supervisor")

multi_agent = builder.compile()
```

---

## 10. Integration with Reflex-Based RAG App

Given the project's existing architecture (Reflex + Docling + Chroma + LangGraph), here's how to integrate these patterns:

### Current State
- `core/document_processor.py` - Docling ingestion
- `core/vector_store.py` - Chroma creation and search
- `core/agent.py` - LangGraph agent factory
- `core/session_registry.py` - Session-scoped objects
- `state/chat_state.py` - Chat history & streaming

### Integration Points

**1. Enhanced Agent Factory (`core/agent.py`):**
```python
# Replace simple ReAct with tiered agent
async def create_document_agent(session_id: str, complexity: str = "auto"):
    if complexity == "simple":
        return create_react_agent(llm, [retrieve_tool])
    elif complexity == "planned":
        return build_plan_execute_agent(llm, [retrieve_tool])
    else:
        # Auto-detect based on query
        return build_tiered_agent(llm, [retrieve_tool])
```

**2. Query Complexity Classifier (`core/query_classifier.py`):**
```python
async def classify_query(query: str) -> str:
    """Classify as 'simple', 'multi_hop', or 'analytical'."""
    prompt = f"Classify this query: {query}\nCategories: simple, multi_hop, analytical"
    result = await llm.ainvoke(prompt)
    return result.content.strip()
```

**3. Reflection Layer (`core/reflection.py`):**
```python
class AnswerValidator:
    async def validate(self, query: str, answer: str, docs: list) -> dict:
        # Check completeness, accuracy, citation quality
        ...
```

**4. Memory Integration (`core/memory.py`):**
```python
class DocumentMemory:
    async def store_interaction(self, session_id: str, query: str, answer: str):
        # Store in Chroma for semantic recall
        ...
    
    async def get_relevant_history(self, session_id: str, query: str):
        # Retrieve past related interactions
        ...
```

### Migration Strategy

1. **Phase 1:** Swap `create_react_agent` with enhanced version supporting multi-step retrieval
2. **Phase 2:** Add plan-and-execute node for complex queries
3. **Phase 3:** Add reflection node for answer quality
4. **Phase 4:** Add long-term memory for user preferences

---

## 11. Key Takeaways

1. **Start Simple:** Begin with ReAct + retrieval, add complexity only when needed
2. **Tool Design Matters:** Invest heavily in tool descriptions and interfaces
3. **Context is King:** Aggressively manage context window; it's your scarcest resource
4. **Verify Everything:** Give the agent ways to check its own work
5. **Plan Before Executing:** For complex tasks, separate planning from execution
6. **Learn from Mistakes:** Reflexion patterns improve performance without fine-tuning
7. **Use Memory Wisely:** Distinguish short-term session memory from long-term knowledge
8. **Human-in-the-Loop:** Always provide escape hatches for human intervention
9. **Measure First:** Add agentic complexity only when it improves metrics
10. **Compose Patterns:** Mix and match patterns (ReAct + Plan-and-Execute + Reflexion) for best results

---

## References

1. Yao, S., et al. (2023). "ReAct: Synergizing Reasoning and Acting in Language Models." ICLR 2023. arXiv:2210.03629
2. Shinn, N., et al. (2023). "Reflexion: Language Agents with Verbal Reinforcement Learning." arXiv:2303.11366
3. Yao, S., et al. (2023). "Tree of Thoughts: Deliberate Problem Solving with Large Language Models." NeurIPS 2023. arXiv:2305.10601
4. Anthropic. (2024). "Building Effective Agents." https://www.anthropic.com/engineering/building-effective-agents
5. Anthropic. (2026). "Best Practices for Claude Code." https://code.claude.com/docs
6. LangChain. (2026). "LangGraph Documentation." https://docs.langchain.com/oss/python/langgraph/
7. LangChain. (2026). "RAG Tutorial with LangChain." https://python.langchain.com/docs/tutorials/rag/
