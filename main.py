"""
Main entrypoint for the ButlerAgent application.
Initializes the toolset based on configuration and runs the voice chat loop.
"""
from tools.base import (CORE_MEMORY_TOOL_IMPLEMENTATION,
                        CORE_MEMORY_TOOL_SCHEMA, CORE_TOOL_IMPLEMENTATIONS,
                        CORE_TOOL_SCHEMAS, OBSIDIAN_FALLBACK_IMPLEMENTATIONS,
                        OBSIDIAN_FALLBACK_SCHEMAS,
                        OBSIDIAN_TOOL_IMPLEMENTATIONS, OBSIDIAN_TOOL_SCHEMAS,
                        get_rag_tools, load_community_tools)
import asyncio
import time

import openai

from agents.butler_agent import ButlerAgent
from config.personality import ASSISTANT_NAME
# --- Import settings ---
from config.settings import (ENABLE_SEMANTIC_SEARCH, IDLE_EXIT_SEC,
                             INCLUDE_OBSIDIAN_TOOLS, STT_MODEL,
                             USE_CORE_MEMORY)
from services.audio_service import play_waiting_music, record
from services.embeddings import EmbeddingService
from services.obsidian_service import save_session_summary
from services.tts_service import speak_custom

# Shared RAG service instance
rag_service = None

def initialize_app_tools():
    """
    Initialize application tools based on configuration settings and return
    a tuple of (tool_implementations, tool_schemas).
    """
    print("\n--- 🛠️  Tools made Available ---")

    # 1. Start with core tools
    final_implementations = dict(CORE_TOOL_IMPLEMENTATIONS)
    final_schemas = list(CORE_TOOL_SCHEMAS)

    # 2. Add community tools
    comm_implementations, comm_schemas = load_community_tools()

    final_implementations.update(comm_implementations)
    final_schemas.extend(comm_schemas)

    # 3. Conditionally add Obsidian-related tools
    if INCLUDE_OBSIDIAN_TOOLS:
        final_implementations.update(OBSIDIAN_TOOL_IMPLEMENTATIONS)
        final_schemas.extend(OBSIDIAN_TOOL_SCHEMAS)

        if USE_CORE_MEMORY:
            # Make sure to import these new variables from tools/base.py
            final_implementations.update(CORE_MEMORY_TOOL_IMPLEMENTATION)
            final_schemas.append(CORE_MEMORY_TOOL_SCHEMA)

        # 3a. Add RAG tools OR the fallback tools
        if ENABLE_SEMANTIC_SEARCH:
            try:
                global rag_service
                rag_service = EmbeddingService()
                rag_implementations, rag_schemas = get_rag_tools(rag_service)
                final_implementations.update(rag_implementations)
                final_schemas.extend(rag_schemas)
            except Exception as e:
                print(f"⚠️ Could not initialize RAG tools: {e}")
                final_implementations.update(OBSIDIAN_FALLBACK_IMPLEMENTATIONS)
                final_schemas.extend(OBSIDIAN_FALLBACK_SCHEMAS)
        else:
            # RAG is disabled, so add the fallback tools
            print("-> RAG disabled. Adding fallback file tools.")
            final_implementations.update(OBSIDIAN_FALLBACK_IMPLEMENTATIONS)
            final_schemas.extend(OBSIDIAN_FALLBACK_SCHEMAS)
    else:
        print("-> Obsidian tools disabled.")

    # --- Final De-duplication and Cleanup ---
    final_unique_schemas = []
    seen_tool_names = set()
    for schema in final_schemas:
        # Normalize community tool schemas lacking the 'function' wrapper key.

        # First, ensure it's a dictionary at all.
        if not isinstance(schema, dict):
            print(
                f"⚠️ Warning: Discarding non-dictionary schema object: {schema}")
            continue

        # If it's missing the 'function' key, it's likely a raw community tool schema.
        if "function" not in schema:
            # Let's normalize it by wrapping it in the expected structure.
            schema = {"type": "function", "function": schema}

        # Now, perform the final validation on the (potentially wrapped) schema
        if "function" not in schema or "name" not in schema.get("function", {}):
            print(
                f"⚠️ Warning: Discarding invalid schema object after normalization: {schema}"
            )
            continue

        name = schema["function"]["name"]
        if name not in seen_tool_names:
            final_unique_schemas.append(schema)
            seen_tool_names.add(name)

    # Replace the potentially corrupted list with the clean, unique one
    final_schemas = final_unique_schemas

    # --- Display the final, active toolset ---
    print("\n--- ✅ Final Active Tools ---")
    # This sorted() call is now safe because we have cleaned the list above
    sorted_tools = sorted(
        final_schemas, key=lambda x: x.get("function", {}).get("name", "")
    )
    for schema in sorted_tools:
        name = schema.get("function", {}).get("name")
        if name:
            print(f"  - {name}")
    print("--------------------------\n")

    # Pass the clean implementation list, filtered by the names in the clean schema list
    final_unique_implementations = {
        name: final_implementations[name]
        for name in seen_tool_names
        if name in final_implementations
    }

    return final_unique_implementations, final_schemas


async def voice_chat(tool_implementations, tool_schemas):
    """
    Main loop for handling voice-driven user interaction. Records audio,
    transcribes it, invokes the ButlerAgent, and handles idle timeouts.

    Args:
        tool_implementations (dict): Available tool implementations.
        tool_schemas (list): Schema definitions for each tool.
    """

    # Preload embedding model and retrievers in background while user is speaking
    embedding_future = None
    if ENABLE_SEMANTIC_SEARCH and rag_service is not None:
        loop = asyncio.get_running_loop()
        embedding_future = loop.run_in_executor(None, rag_service.load)

    # Butler's greeting log
    print(
        f"👋 Hello! I'm your butler {ASSISTANT_NAME}. How can I assist you today?")

    agent = ButlerAgent(tool_implementations, tool_schemas)
    last_user_ts = time.monotonic()

    while True:
        # Check for idle timeout
        if time.monotonic() - last_user_ts > IDLE_EXIT_SEC:
            print("👋 Idle timeout reached. Shutting down.")
            if not getattr(agent, "private_chat", False):
                save_session_summary(agent.history)
            return

        print("🎙 Listening…", end="\r", flush=True)
        wav = await record()
        if wav is None:
            continue

        try:
            stt_resp = openai.audio.transcriptions.create(
                file=open(wav, "rb"),
                model=STT_MODEL,
                response_format="text",
                language="en",
            )
            user = stt_resp.strip()
        except Exception as e:
            print(f"[stt-error] {e}")
            continue

        if not user:
            continue

        last_user_ts = time.monotonic()
        print(" " * 40, end="\r")
        print(f"👤 {user}")

        print("🤖 (thinking…)", end="\r", flush=True)
        stop_chime = asyncio.Event()
        music_task = asyncio.create_task(play_waiting_music(stop_chime))

        # Wait for embeddings model to finish loading before processing
        if embedding_future:
            await embedding_future

        reply = await agent.run([{"role": "user", "content": user}])

        print(" " * 40, end="\r")
        if reply.strip():
            print(f"🤖 {reply}")
            await speak_custom(reply, stop_chime)
        else:
            stop_chime.set()

        await music_task
        last_user_ts = time.monotonic()

        # Check exit conditions
        if agent.exit_requested:
            print("👋 Exit requested by quit_chat tool. Shutting down.")
            if not agent.private_chat:
                save_session_summary(agent.history)
            return

        if agent.reset_requested:
            print("🔄 Chat reset requested. Starting a fresh conversation.")
            if not agent.private_chat:
                save_session_summary(agent.history)
            agent = ButlerAgent()
            last_user_ts = time.monotonic()
            continue


if __name__ == "__main__":
    # The application setup now happens here, once.
    tool_implementations, tool_schemas = initialize_app_tools()

    try:
        # The final toolset is passed into the main application loop.
        asyncio.run(voice_chat(tool_implementations, tool_schemas))
    except KeyboardInterrupt:
        print("\n👋 Exiting by Ctrl‑C")
