"""
Main entrypoint for the ButlerAgent application.
Initializes the toolset based on configuration and runs the voice chat loop.
"""
from tools.loader import initialize_app_tools
from tools.config_loader import get_settings
import asyncio
import time

import openai

from agents.butler_agent import ButlerAgent
from config.personality import ASSISTANT_NAME
# --- Import settings ---
from config.settings import (IDLE_EXIT_SEC,
                             STT_MODEL,
                             TTS_IN_PARALLEL)
from services.audio_service import play_waiting_music, record
from services.embeddings import EmbeddingService
from services.obsidian_service import save_session_summary
from services.tts_service import speak_custom, speak_parallel

async def initialize_app():
    """
    Initialize the application tools and RAG service.
    
    Returns:
        Tuple of (agent, embedding_future)
    """
    # Preload embedding model and retrievers in background
    rag_service = None
    embedding_future = None
    
    tool_settings = get_settings()
    
    if tool_settings["use_semantic_search"]:
        rag_service = EmbeddingService()
        loop = asyncio.get_running_loop()
        embedding_future = loop.run_in_executor(None, rag_service.load)
    
    # Get the tools and create the ButlerAgent
    tool_implementations, tool_schemas = await initialize_app_tools(rag_service)
    agent = ButlerAgent(tool_implementations, tool_schemas)

    return agent, embedding_future

async def voice_chat(agent, embedding_future=None):
    """
    Main loop for handling voice-driven user interaction. Records audio,
    transcribes it, invokes the ButlerAgent, and handles idle timeouts.

    Args:
        agent: Initialized Butler Agent.
        embedding_future: Optional future for embedding model loading.
    """

    # Butler's greeting log
    print(
        f"👋 Hello! I'm your butler {ASSISTANT_NAME}. How can I assist you today?")

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
            embedding_future = None

        reply = await agent.run([{"role": "user", "content": user}])

        print(" " * 40, end="\r")
        if reply.strip():
            print(f"🤖 {reply}")
            
            # Measure TTS timing
            tts_start = time.time()
            if TTS_IN_PARALLEL:
                timing = await speak_parallel(reply, stop_chime)
                print(f"   ⏱️ TTS: {timing['first_chunk']:.1f}s first, {timing['total']:.1f}s total")
            else:
                await speak_custom(reply, stop_chime)
                tts_end = time.time()
                print(f"   ⏱️ TTS: {tts_end - tts_start:.1f}s")
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
            agent = ButlerAgent(agent.tool_implementations, agent.tool_schemas)
            last_user_ts = time.monotonic()
            continue

async def main():
    """Main entry point that handles initialization and starts the chat loop."""
    
    agent, embedding_future = await initialize_app()
    await voice_chat(agent, embedding_future)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Exiting by Ctrl‑C")
