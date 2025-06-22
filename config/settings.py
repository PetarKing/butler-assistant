"""
Configuration settings for the Butler Agent voice chat application.

This module loads environment variables and defines constants for:
- Audio processing settings
- AI model configurations
- File system paths for Obsidian integration
- Tool loading and configuration
- Semantic search settings
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

# Audio processing settings
RATE, CHUNK = 16000, 1024
VOICE_ID = os.getenv("CARTESIA_VOICE_ID")

# AI model configurations
MODEL_NAME = os.getenv("OPENAI_MODEL", "o4-mini-2025-04-16")
HIGH_POWER_MODEL = os.getenv("OPENAI_MODEL_HIGH", "o3-2025-04-16")
CHEAP_MODEL = os.getenv("CHEAP_MODEL", "gpt-3.5-turbo-0125")

# Audio feedback settings
WAITING_WAV = os.getenv("WAITING_WAV", "waiting.wav")
WAITING_VOLUME = float(os.getenv("WAITING_VOLUME", "0.3"))

# Voice processing timing
IDLE_EXIT_SEC = float(os.getenv("IDLE_TIMEOUT_SEC", "30"))
TRAILING_SILENCE_SEC = float(os.getenv("TRAILING_SILENCE_SEC", "1.5"))
ENERGY_THRESHOLD = int(os.getenv("ENERGY_THRESHOLD", "350"))
MAX_RECORD_SEC = int(os.getenv("MAX_RECORD_SEC", "90"))

# Voice Activity Detection settings
VAD_FRAME_MS = int(os.getenv("VAD_FRAME_MS", "30"))
VAD_AGGRESSIVENESS = int(os.getenv("VAD_AGGRESSIVENESS", "2"))

# Debug settings
DEBUG_AUDIO = os.getenv("DEBUG_AUDIO", "false").lower() in ("1", "true", "yes")

# Community tools configuration
_tools_env_string = os.getenv("COMMUNITY_TOOLS_TO_LOAD")
if _tools_env_string:
    COMMUNITY_TOOLS_TO_LOAD = [tool.strip() for tool in _tools_env_string.split(',')]
else:
    COMMUNITY_TOOLS_TO_LOAD = []

# Tool-specific configuration overrides
TOOL_CONFIG_OVERRIDES = {
    # Example: Tool configuration with custom initialization arguments
    # "GoogleSearchRun": {
    #     "init_args": {
    #         "api_key": os.getenv("GOOGLE_API_KEY"),
    #         "search_engine_id": os.getenv("GOOGLE_CSE_ID")
    #     }
    # }
}

# Obsidian vault integration settings
INCLUDE_OBSIDIAN_TOOLS = os.getenv("INCLUDE_OBSIDIAN_TOOLS", "true").lower() in ("1", "true", "yes")
VAULT_ROOT = Path(os.getenv("OBSIDIAN_VAULT_PATH")).expanduser().resolve()
AGENT_FOLDER_NAME = os.getenv("AGENT_FOLDER_NAME", "Butler")
ASSISTANT_NAME = os.getenv("ASSISTANT_NAME", "Sebastian")

# Agent workspace paths
SANDBOX_ROOT = (VAULT_ROOT / AGENT_FOLDER_NAME).resolve()
LOG_SUBDIR = SANDBOX_ROOT / "logs"
LOG_SUBDIR.mkdir(parents=True, exist_ok=True)

# Logging configuration
TOOL_CALL_FILE_NAME = os.getenv("TOOL_CALL_FILE_NAME", "tool-calls.md")
TOOL_CALL_LOG_PATH = LOG_SUBDIR / TOOL_CALL_FILE_NAME
SUMMARY_PREFIX = os.getenv("SESSION_SUMMARY_PREFIX", "session-summary-")

# Core memory feature settings
USE_CORE_MEMORY = os.getenv("USE_CORE_MEMORY", "false").lower() == "true"
CORE_MEMORY_FILENAME = os.getenv("CORE_MEMORY_FILENAME", "_core_memory.md")

# Text-to-Speech and Speech-to-Text settings
TTS_MODEL = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
TTS_VOICE = os.getenv("OPENAI_TTS_VOICE", "alloy")
STT_MODEL = os.getenv("OPENAI_STT_MODEL", "gpt-4o-mini-transcribe")

# API keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Semantic search and RAG settings
ENABLE_SEMANTIC_SEARCH = os.getenv("ENABLE_SEMANTIC_SEARCH", "false").lower() == "true"
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "cached/obsidian_chroma_db")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "thenlper/gte-large")
SEMANTIC_SEARCH_K_VALUE = int(os.getenv("SEMANTIC_SEARCH_K_VALUE", 5))

def print_obsidian_paths() -> None:
    """
    Print diagnostic information about Obsidian-related file paths.
    
    Useful for debugging configuration issues and verifying that
    the vault and sandbox directories are correctly set up.
    """
    print(f"🔖 Obsidian Vault Root     : {VAULT_ROOT}")
    print(f"📂 Sandbox Folder         : {SANDBOX_ROOT}")
    print(f"🗄️ Logs Subfolder          : {LOG_SUBDIR}")
    print(f"📝 Tool-call Log File      : {TOOL_CALL_LOG_PATH}")
    print(f"📄 Core Memory Note        : {CORE_MEMORY_FILENAME}")
