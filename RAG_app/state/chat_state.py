"""
Chat state for managing conversation flow.
Handles streaming responses from the LLM agent.
"""
import reflex as rx
import asyncio
from typing import List
from pydantic import BaseModel
from ..services import get_llm_service


class QA(BaseModel):
    """Question-Answer pair model"""
    question: str
    answer: str


class ChatState(rx.State):
    """State management for chat interface"""
    
    # Chat history
    chat_history: List[QA] = []
    
    # Current input
    current_question: str = ""
    
    # Streaming status
    is_streaming: bool = False
    
    # Thread ID for conversation memory
    thread_id: str = "main_conversation"
    
    @rx.event
    def set_question(self, value: str):
        """Bind input field value"""
        self.current_question = value
    
    @rx.event
    def handle_key_down(self, key: str):
        """Handle Enter key press to submit"""
        if key == "Enter":
            return ChatState.process_question
    
    @rx.event
    def clear_history(self):
        """Clear chat history"""
        self.chat_history = []
        llm_service = get_llm_service()
        llm_service.reset()
    
    @rx.event(background=True)
    async def process_question(self):
        """
        Process user question with streaming response.
        Background task to handle async LLM streaming.
        """
        # Lock 1: Capture input and setup
        async with self:
            if not self.current_question.strip():
                return
            
            question_text = self.current_question
            self.current_question = ""
            self.is_streaming = True
            
            # Add empty answer placeholder
            self.chat_history.append(QA(question=question_text, answer=""))
        
        # Get LLM service
        llm_service = get_llm_service()
        
        if not llm_service.agent:
            async with self:
                self.chat_history[-1].answer = "⚠️ Please upload and process documents first before asking questions."
                self.is_streaming = False
            return
        
        try:
            # Stream response
            accumulated_answer = ""
            
            async for token in llm_service.stream_response(
                question_text,
                self.thread_id
            ):
                accumulated_answer += token
                
                # Lock 2: Update answer incrementally
                async with self:
                    self.chat_history[-1].answer = accumulated_answer
                
                # Small delay for smooth streaming
                await asyncio.sleep(0.02)
            
        except Exception as e:
            print(f"Chat error: {e}")
            async with self:
                self.chat_history[-1].answer = f"❌ Error: {str(e)}"
        
        finally:
            # Lock 3: Finalize
            async with self:
                self.is_streaming = False
