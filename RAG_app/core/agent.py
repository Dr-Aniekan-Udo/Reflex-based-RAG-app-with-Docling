"""
LangGraph agent configuration and setup using the Core API (StateGraph).
"""
from typing import Literal, List
from langchain_core.tools import BaseTool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

SYSTEM_PROMPT = """You are a helpful document intelligence assistant. You have access to documents that have been uploaded and processed.

GUIDELINES:
- Use the search_documents tool to find relevant information.
- Be efficient: one well-crafted search is usually sufficient.
- Provide clear, accurate answers based on the document contents.
- Always cite your sources with filenames and page numbers (e.g., 'Source: Book.pdf (Page 42)').
- If information isn't found, say so clearly.
- Be concise but thorough

When answering:
1. Search the documents with a focused query
2. Synthesize a clear answer from the results
3. Include source citations (filenames)
4. Only search again if absolutely necessary
"""


def create_documentation_agent(tools: List[BaseTool], model_name: str = "gemini-2.5-flash"):
    """
    Create a document intelligence assistant using the core LangGraph StateGraph.
    """
    llm = ChatGoogleGenerativeAI(model=model_name, temperature=0)
    llm_with_tools = llm.bind_tools(tools)

    def call_model(state: MessagesState):
        messages = state["messages"]
        if not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    def should_continue(state: MessagesState) -> Literal["tools", END]:
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            return "tools"
        return END

    workflow = StateGraph(MessagesState)
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", should_continue)
    workflow.add_edge("tools", "agent")

    memory = MemorySaver()
    agent = workflow.compile(checkpointer=memory)
    return agent
