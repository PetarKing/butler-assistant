"""
Butler Agent implementation with tool integration and memory management.

This module contains the main ButlerAgent class that handles conversation
processing, tool execution, and memory management for the voice assistant.
"""

import asyncio
import inspect
import json

import openai
from langchain_core.tools import BaseTool

from config.personality import SYSTEM_PROMPT
from config.settings import (AGENT_FOLDER_NAME, CORE_MEMORY_FILENAME,
                             HIGH_POWER_MODEL, MODEL_NAME, USE_CORE_MEMORY)
from services.obsidian_service import read_note, recent_session_summaries
from utils.logging import log_tool_call


class ButlerAgent:
    """
    AI agent with tool capabilities and memory management.

    This class manages conversation flow, tool execution, and maintains
    conversation history with optional core memory and session summaries.

    Attributes:
        system_msg (dict): System message defining the agent's personality
        history (list): Conversation history including system messages
        model_name (str): Current AI model being used
        exit_requested (bool): Flag indicating user wants to end conversation
        reset_requested (bool): Flag indicating user wants to reset conversation
        private_chat (bool): Flag indicating private mode (no note writing)
        tool_implementations (dict): Available tool functions and implementations
        tool_schemas (list): Tool schema definitions for OpenAI API
    """

    def __init__(self, tool_implementations, tool_schemas):
        """
        Initialize the Butler Agent with tools and memory.

        Args:
            tool_implementations (dict): Dictionary mapping tool names to implementations
            tool_schemas (list): List of tool schema definitions for OpenAI API
        """
        self.system_msg = {
            "role": "system",
            "content": SYSTEM_PROMPT,
        }
        self.history = [self.system_msg]
        self.model_name = MODEL_NAME
        self.exit_requested = False
        self.reset_requested = False
        self.private_chat = False

        self.tool_implementations = tool_implementations
        self.tool_schemas = tool_schemas

        self._load_core_memory()
        self._load_recent_memories()

    def _load_core_memory(self):
        """Load core memory from the designated file if enabled."""
        if not USE_CORE_MEMORY:
            return
        try:
            core_memory_content = read_note(
                f"{AGENT_FOLDER_NAME}/{CORE_MEMORY_FILENAME}"
            )

            if not core_memory_content.startswith("[read_note-error]"):
                core_memory_message = {
                    "role": "system",
                    "content": f"--- CORE MEMORY & STANDING INSTRUCTIONS ---\n{core_memory_content}\n--- END CORE MEMORY ---",
                }
                self.history.append(core_memory_message)
                print("✅ Core memory loaded successfully.")
            else:
                print(f"⚠️ Could not load core memory: {core_memory_content}")
        except Exception as e:
            print(
                f"⚠️ An unexpected error occurred while loading core memory: {e}")

    def _load_recent_memories(self):
        """Load recent session summaries to provide context."""
        try:
            _memories_to_load = 3
            memories = recent_session_summaries(_memories_to_load)
            if memories.strip():
                self.history.append(
                    {
                        "role": "system",
                        "content": f"Here are highlighted notes from recent sessions:\n{memories}",
                    }
                )
                print(f"✅ Last {_memories_to_load} chat summaries loaded successfully.")
        except Exception as e:
            print(f"[memory-load-error] {e}")

    async def run(self, conversation):
        """
        Process a conversation turn and return the assistant's response.

        Args:
            conversation (list): List of conversation messages

        Returns:
            str: The assistant's response text
        """
        if conversation and conversation[-1]["role"] == "user":
            self.history.append(conversation[-1])

        response = await asyncio.to_thread(
            openai.chat.completions.create,
            model=self.model_name,
            messages=self.history,
            tools=self.tool_schemas,
            tool_choice="auto",
        )

        # Handle tool calls iteratively until completion
        while response.choices[0].finish_reason == "tool_calls":
            self.history.append(response.choices[0].message)

            tool_msgs = await asyncio.gather(
                *(
                    self._execute_tool_call(call)
                    for call in response.choices[0].message.tool_calls
                )
            )
            self.history.extend(tool_msgs)

            response = await asyncio.to_thread(
                openai.chat.completions.create,
                model=self.model_name,
                messages=self.history,
                tools=self.tool_schemas,
                tool_choice="auto",
            )

        assistant_reply = response.choices[0].message.content.strip()
        self.history.append({"role": "assistant", "content": assistant_reply})
        return assistant_reply

    async def _execute_tool_call(self, call):
        """
        Execute a single tool call and return the result message.

        Args:
            call: OpenAI tool call object

        Returns:
            dict: Tool result message for conversation history
        """
        tname = call.function.name
        targs = json.loads(call.function.arguments)

        # Handle special mode switches
        if tname == "quit_chat":
            self.exit_requested = True
        elif tname == "reset_chat":
            self.reset_requested = True
        elif tname == "enable_high_brain_power":
            self.model_name = HIGH_POWER_MODEL
        elif tname == "enable_private_mode":
            self.private_chat = True

        func_or_tool = self.tool_implementations.get(tname)

        # Block note writing in private mode
        if self.private_chat and tname in ("append_note", "append_core_memory"):
            result = "[Action Blocked] Cannot write to notes while in private mode."
        elif not func_or_tool:
            result = f"unknown tool: {tname}"
        else:
            try:
                is_async = inspect.iscoroutinefunction(func_or_tool)
                # Check if the function we retrieved is an async function
                if is_async:
                    # Await the coroutine function with unpacked keyword arguments
                    result = await func_or_tool(**targs)
                elif isinstance(func_or_tool, BaseTool):
                    # Execute LangChain tool
                    result = await asyncio.to_thread(func_or_tool.invoke, targs)
                else:
                    # Execute regular function
                    result = await asyncio.to_thread(func_or_tool, **targs)
            except Exception as e:
                result = f"[{tname}-error] {e}"

        log_tool_call(tname, targs, result)
        return {
            "role": "tool",
            "tool_call_id": call.id,
            "content": str(result),
        }
