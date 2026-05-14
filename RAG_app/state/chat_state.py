import reflex as rx
import asyncio
import uuid
from typing import List, Dict

from ..core.session_registry import get_registry
from ..core.logging_config import logger
from .base_state import BaseState


class ChatState(BaseState):
    """State management for chat interface."""

    chat_history: List[Dict[str, str]] = []
    current_question: str = ""
    is_streaming: bool = False
    thread_id: str = "main_conversation"

    @rx.event
    def set_question(self, value: str):
        self.current_question = value

    @rx.event
    def handle_key_down(self, key: str):
        if key == "Enter":
            return ChatState.process_question

    @rx.event
    def clear_history(self):
        logger.info("chat_clear_history", session_id=self.session_id, old_thread=self.thread_id)
        self.chat_history = []
        # Rotate thread_id to wipe conversation memory for this session only
        self.thread_id = str(uuid.uuid4())

    @rx.event(background=True)
    async def process_question(self):
        logger.info("process_question_called", session_id=self.session_id, question=self.current_question[:50])

        async with self:
            if not self.current_question.strip():
                logger.warning("process_question_empty", session_id=self.session_id)
                return
            question_text = self.current_question
            self.current_question = ""
            self.is_streaming = True
            self.chat_history.append({"role": "user", "content": question_text})
            self.chat_history.append({"role": "assistant", "content": ""})
            logger.info("chat_message_added", session_id=self.session_id, question=question_text[:50])

        registry = get_registry()
        entry = registry.get(self.session_id)
        agent = entry.get("agent")

        if not agent:
            async with self:
                self.chat_history[-1]["content"] = "⚠️ Please upload and process documents first before asking questions."
                self.is_streaming = False
            logger.warning("chat_no_agent", session_id=self.session_id)
            return

        config = {"configurable": {"thread_id": self.thread_id}}
        accumulated = ""

        try:
            from langchain_core.messages import HumanMessage

            logger.info("agent_stream_start", session_id=self.session_id, thread_id=self.thread_id)
            async for msg, metadata in agent.astream(
                {"messages": [HumanMessage(content=question_text)]},
                config=config,
                stream_mode="messages"
            ):
                langgraph_node = metadata.get("langgraph_node", "")
                if "tools" in langgraph_node.lower() or "tool" in langgraph_node.lower():
                    continue

                if "agent" in langgraph_node.lower() and hasattr(msg, "content"):
                    raw_content = msg.content
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
                        accumulated += content
                        async with self:
                            self.chat_history[-1]["content"] = accumulated
                        await asyncio.sleep(0.02)

            logger.info("agent_stream_complete", session_id=self.session_id, response_length=len(accumulated))

        except Exception as e:
            logger.error("chat_error", error=str(e), session_id=self.session_id, exc_info=True)
            async with self:
                self.chat_history[-1]["content"] = f"❌ Error: {str(e)}"

        finally:
            async with self:
                self.is_streaming = False
