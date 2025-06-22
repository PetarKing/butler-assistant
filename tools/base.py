"""
Tool registry and configuration for the Butler Agent.

This module centralizes all tool definitions, schemas, and loading logic.
Tools are organized into categories: core, Obsidian, semantic search, and community tools.
"""

from langchain_community import tools as community_tools
from langchain_core.utils.function_calling import convert_to_openai_function

from config.settings import COMMUNITY_TOOLS_TO_LOAD, SANDBOX_ROOT
from services.obsidian_service import (append_core_memory, append_note,
                                       list_vault_files, read_entire_memory,
                                       read_note)

from .chat_tools import (enable_high_brain_power, enable_private_mode,
                         quit_chat, reset_chat)
from .semantic_search import (build_filtered_semantic_search,
                              build_semantic_search)
from .system_tools import clipboard_content, screen_capture
from .web_tools import calculator, fetch_page, web_search

# ==========================================================================
# CORE TOOLS - Always available across all configurations
# ==========================================================================

CORE_TOOL_IMPLEMENTATIONS = {
    "quit_chat": quit_chat,
    "reset_chat": reset_chat,
    "web_search": web_search,
    "calculator": calculator,
    "fetch_page": fetch_page,
    "screen_capture": screen_capture,
    "clipboard_content": clipboard_content,
    "enable_high_brain_power": enable_high_brain_power,
    "enable_private_mode": enable_private_mode,
}

CORE_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "reset_chat",
            "description": "Clear the conversation so a new chat can start.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "quit_chat",
            "description": "End the conversation and shut down the program.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web and return a short snippet.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Evaluate a basic arithmetic expression.",
            "parameters": {
                "type": "object",
                "properties": {"expression": {"type": "string"}},
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_page",
            "description": "Download a web page and return its plain‑text content with AI summary.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "screen_capture",
            "description": "Take a screenshot and return an AI description of its contents.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "clipboard_content",
            "description": "Return clipboard text or AI summary of clipboard image.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "enable_high_brain_power",
            "description": "Switch to the high-performance model for complex tasks.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "enable_private_mode",
            "description": "Mark this conversation as private (no Butler Log will be created).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]

# ==========================================================================
# OBSIDIAN TOOLS - File system and note management
# ==========================================================================

OBSIDIAN_TOOL_IMPLEMENTATIONS = {
    "append_note": append_note,
    "read_note": read_note,
}

OBSIDIAN_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_note",
            "description": "Read the raw markdown content of a specific note. Use semantic_search first to find relevant paths.",
            "parameters": {
                "type": "object",
                "properties": {"rel_path": {"type": "string"}},
                "required": ["rel_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "append_note",
            "description": f'Append markdown content to a note in the sandbox folder "{SANDBOX_ROOT}". Path should be relative to sandbox root.',
            "parameters": {
                "type": "object",
                "properties": {
                    "rel_path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["rel_path", "content"],
            },
        },
    },
]

# ==========================================================================
# CORE MEMORY TOOL - Persistent assistant memory
# ==========================================================================

CORE_MEMORY_TOOL_IMPLEMENTATION = {"append_core_memory": append_core_memory}

CORE_MEMORY_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "append_core_memory",
        "description": (
            "Update core memory with key facts, user preferences, or instructions. "
            "Use for important information that should persist across conversations. "
            "Write in first person as if making a note to yourself."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The important information to remember.",
                }
            },
            "required": ["content"],
        },
    },
}

# ==========================================================================
# FALLBACK TOOLS - Used when RAG is disabled
# ==========================================================================

OBSIDIAN_FALLBACK_IMPLEMENTATIONS = {
    "read_entire_memory": read_entire_memory,
    "list_vault_files": list_vault_files,
}

OBSIDIAN_FALLBACK_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_entire_memory",
            "description": "Return all session-summary memory files. Less effective than semantic_search.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_vault_files",
            "description": "List all Markdown files in the vault. Use when semantic search is unavailable.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]

# ==========================================================================
# SEMANTIC SEARCH TOOLS - RAG-powered search capabilities
# ==========================================================================


def get_rag_tools(rag_service):
    """
    Get semantic search tool implementations and schemas.

    Args:
        rag_service: Initialized embedding service for semantic search

    Returns:
        Tuple of (implementations_dict, schemas_list)
    """
    implementations = {
        "semantic_search": build_semantic_search(rag_service),
        "filtered_semantic_search": build_filtered_semantic_search(rag_service),
    }

    schemas = [
        {
            "type": "function",
            "function": {
                "name": "semantic_search",
                "description": "Search the Obsidian vault for conceptually related content using semantic similarity.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "use_compression": {
                            "type": "boolean",
                            "description": "Return more concise results.",
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "filtered_semantic_search",
                "description": "Semantic search filtered by specific tags for focused queries.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "tag": {
                            "type": "string",
                            "description": "Tag to filter by (without '#' prefix).",
                        },
                    },
                    "required": ["query", "tag"],
                },
            },
        },
    ]
    return implementations, schemas


# ==========================================================================
# COMMUNITY TOOLS - LangChain community tool integration
# ==========================================================================


def load_community_tools():
    """
    Load community tools based on configuration.

    Returns:
        Tuple of (implementations_dict, schemas_list)
    """
    implementations = {}
    schemas = []

    if not isinstance(COMMUNITY_TOOLS_TO_LOAD, list) or not COMMUNITY_TOOLS_TO_LOAD:
        return implementations, schemas

    for tool_name in COMMUNITY_TOOLS_TO_LOAD:
        try:
            tool_class = getattr(community_tools, tool_name)
            tool_instance = tool_class()
            implementations[tool_instance.name] = tool_instance
            schemas.append(convert_to_openai_function(tool_instance))
        except Exception as e:
            print(f"Failed to load community tool '{tool_name}': {e}")
            raise e

    return implementations, schemas
