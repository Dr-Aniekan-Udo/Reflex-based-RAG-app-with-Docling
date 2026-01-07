"""
LLM Service with LangGraph agent integration.
Manages the conversational AI agent with document search capabilities.
"""
from typing import Literal, AsyncGenerator
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from dotenv import load_dotenv

from .vector_store import get_vector_store


# System prompt for the agent
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


class LLMService:
    """Singleton service for LLM operations"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.agent = None
        self.memory = MemorySaver()
        self._initialized = True
    
    def _create_search_tool(self):
        """Create the document search tool"""
        vector_store = get_vector_store()
        
        @tool
        async def search_documents(query: str) -> str:
            """
            Search the uploaded documents for relevant information.
            Use this tool when you need to find specific information from the uploaded documents.
            
            Args:
                query: The search query or question about the documents
            """
            try:
                results = await vector_store.search(query, k=8)
                
                if not results:
                    return "No relevant information found in the documents for this query."
                
                context_parts = []
                for i, doc in enumerate(results, 1):
                    source = doc.metadata.get('filename', doc.metadata.get('source', 'Unknown source'))
                    page = doc.metadata.get('page', 'Unknown Page')
                    content = doc.page_content.strip()
                    
                    context_parts.append(
                        f"[Source {i}: {source} (Page {page})]\n"
                        f"Content: {content}\n"
                    )
                
                return "\n---\n".join(context_parts)
                
            except Exception as e:
                return f"Error searching documents: {str(e)}"
        
        return search_documents
    
    def create_agent(self, model_name: str = "gemini-2.5-flash"):
        """Create the LangGraph agent"""
        
        # Load environment variables
        load_dotenv()
        
        # Create LLM
        llm = ChatGoogleGenerativeAI(model=model_name, temperature=0)
        
        # Create tool
        search_tool = self._create_search_tool()
        tools = [search_tool]
        
        # Bind tools to LLM
        llm_with_tools = llm.bind_tools(tools)
        
        # Define agent node
        def call_model(state: MessagesState):
            messages = state["messages"]
            
            # Ensure system prompt is first
            if not isinstance(messages[0], SystemMessage):
                messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
            
            response = llm_with_tools.invoke(messages)
            return {"messages": [response]}
        
        # Define routing logic
        def should_continue(state: MessagesState) -> Literal["tools", END]:
            messages = state["messages"]
            last_message = messages[-1]
            
            if last_message.tool_calls:
                return "tools"
            return END
        
        # Build graph
        workflow = StateGraph(MessagesState)
        workflow.add_node("agent", call_model)
        workflow.add_node("tools", ToolNode(tools))
        
        workflow.add_edge(START, "agent")
        workflow.add_conditional_edges("agent", should_continue)
        workflow.add_edge("tools", "agent")
        
        # Compile with memory
        self.agent = workflow.compile(checkpointer=self.memory)
    
    async def stream_response(self, question: str, thread_id: str = "default") -> AsyncGenerator[str, None]:
        """
        Stream response from the agent.
        
        Args:
            question: User question
            thread_id: Thread ID for conversation memory
            
        Yields:
            Response tokens
        """
        if not self.agent:
            yield "Agent not initialized. Please process documents first."
            return
        
        config = {"configurable": {"thread_id": thread_id}}
        
        try:
            async for msg, metadata in self.agent.astream(
                {"messages": [HumanMessage(content=question)]},
                config=config,
                stream_mode="messages"
            ):
                langgraph_node = metadata.get("langgraph_node", "")
                
                # Skip tool outputs
                if "tools" in langgraph_node.lower() or "tool" in langgraph_node.lower():
                    continue
                
                # Stream from agent node only
                if "agent" in langgraph_node.lower() and hasattr(msg, "content"):
                    raw_content = msg.content
                    
                    # Handle Gemini's list-based content
                    content = ""
                    if isinstance(raw_content, list):
                        for part in raw_content:
                            if isinstance(part, dict) and "text" in part:
                                content += part["text"]
                            elif isinstance(part, str):
                                content += part
                    else:
                        content = str(raw_content)
                    
                    if content:
                        yield content
                        
        except Exception as e:
            yield f"Error: {str(e)}"
    
    def reset(self):
        """Reset the agent"""
        self.agent = None
        self.memory = MemorySaver()


# Global instance
def get_llm_service() -> LLMService:
    """Get the singleton LLM service instance"""
    return LLMService()
