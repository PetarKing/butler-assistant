"""
Master tool loader orchestrating all tool loading.

Consolidates tool loading based on configuration and provides unified access
to all tools for the Butler Agent.
"""
from .internal_tools_registry import (
    CORE_TOOL_IMPLEMENTATIONS, CORE_TOOL_SCHEMAS,
    OBSIDIAN_TOOL_IMPLEMENTATIONS, OBSIDIAN_TOOL_SCHEMAS,
    OBSIDIAN_FALLBACK_IMPLEMENTATIONS, OBSIDIAN_FALLBACK_SCHEMAS,
    CORE_MEMORY_TOOL_IMPLEMENTATION, CORE_MEMORY_TOOL_SCHEMA,
    get_rag_tools
)

from .config_loader import (
    get_settings,
    get_tool_names_from_section,
    get_community_tools_config,
    get_mcp_servers_config
)

from .external_tool_loaders import (
    load_community_tools,
    load_mcp_tools
)

async def initialize_app_tools(rag_service):
    """
    Initialize application tools based on configuration settings and return
    a tuple of (tool_implementations, tool_schemas).
    """
    print("\n--- 🛠️  Tools made Available ---")

    # Get global settings
    settings = get_settings()
    INCLUDE_OBSIDIAN_TOOLS = settings.get("include_obsidian_tools", True)
    USE_CORE_MEMORY = settings.get("use_core_memory", False)
    USE_MCP_TOOLS = settings.get("use_mcp_tools", False)
    USE_SEMANTIC_SEARCH = settings.get("use_semantic_search", False)

    final_implementations = {}
    final_schemas = []

    # 1. Load internal core tools
    enabled_core_tools = get_tool_names_from_section('core_tools')
    
    # Only add core tools that are enabled in the config
    for tool_name, impl in CORE_TOOL_IMPLEMENTATIONS.items():
        if tool_name in enabled_core_tools:
            final_implementations[tool_name] = impl
    
    for schema in CORE_TOOL_SCHEMAS:
        if "function" in schema and schema["function"]["name"] in enabled_core_tools:
            final_schemas.append(schema)
    
    # 2. Load community tools
    community_tool_configs = get_community_tools_config()
    comm_implementations, comm_schemas = await load_community_tools(community_tool_configs)
    
    final_implementations.update(comm_implementations)
    final_schemas.extend(comm_schemas)

    # 3. Load MCP tools if enabled
    if USE_MCP_TOOLS:
        mcp_server_configs = get_mcp_servers_config()
        try:
            mcp_implementations, mcp_schemas = await load_mcp_tools(mcp_server_configs)
            final_implementations.update(mcp_implementations)
            final_schemas.extend(mcp_schemas)
            print(f"🧰 Following MCP tools are available: {list(mcp_implementations.keys())}")
        except Exception as e:
            print(f"⚠️ Could not initialize MCP tools: {e}")

    # 4. Load Obsidian-related tools
    if INCLUDE_OBSIDIAN_TOOLS:
        # Get enabled obsidian tools
        enabled_obsidian_tools = get_tool_names_from_section('obsidian_tools')
        
        # Add enabled obsidian tools
        for tool_name, impl in OBSIDIAN_TOOL_IMPLEMENTATIONS.items():
            if tool_name in enabled_obsidian_tools:
                final_implementations[tool_name] = impl
        
        for schema in OBSIDIAN_TOOL_SCHEMAS:
            if "function" in schema and schema["function"]["name"] in enabled_obsidian_tools:
                final_schemas.append(schema)

        # Add core memory tools if enabled
        if USE_CORE_MEMORY:
            enabled_memory_tools = get_tool_names_from_section('memory_tools')
            
            for tool_name, impl in CORE_MEMORY_TOOL_IMPLEMENTATION.items():
                if tool_name in enabled_memory_tools:
                    final_implementations[tool_name] = impl
            
            if "function" in CORE_MEMORY_TOOL_SCHEMA and CORE_MEMORY_TOOL_SCHEMA["function"]["name"] in enabled_memory_tools:
                final_schemas.append(CORE_MEMORY_TOOL_SCHEMA)

        # Add RAG tools or fallback tools
        if rag_service and USE_SEMANTIC_SEARCH:
            try:
                rag_implementations, rag_schemas = get_rag_tools(rag_service)
                final_implementations.update(rag_implementations)
                final_schemas.extend(rag_schemas)
            except Exception as e:
                print(f"⚠️ Could not initialize RAG tools: {e}")
                # Fall back to enabled fallback tools
                enabled_fallback_tools = get_tool_names_from_section('fallback_tools')
                
                for tool_name, impl in OBSIDIAN_FALLBACK_IMPLEMENTATIONS.items():
                    if tool_name in enabled_fallback_tools:
                        final_implementations[tool_name] = impl
                
                for schema in OBSIDIAN_FALLBACK_SCHEMAS:
                    if "function" in schema and schema["function"]["name"] in enabled_fallback_tools:
                        final_schemas.append(schema)
        else:
            # RAG is disabled, so add the fallback tools
            print("-> RAG disabled. Adding fallback file tools.")
            enabled_fallback_tools = get_tool_names_from_section('fallback_tools')
            
            for tool_name, impl in OBSIDIAN_FALLBACK_IMPLEMENTATIONS.items():
                if tool_name in enabled_fallback_tools:
                    final_implementations[tool_name] = impl
            
            for schema in OBSIDIAN_FALLBACK_SCHEMAS:
                if "function" in schema and schema["function"]["name"] in enabled_fallback_tools:
                    final_schemas.append(schema)
    else:
        print("-> Obsidian tools disabled.")

    # --- Final De-duplication and Cleanup ---
    final_unique_schemas = []
    seen_tool_names = set()
    for schema in final_schemas:
        # Normalize community tool schemas lacking the 'function' wrapper key.
        if not isinstance(schema, dict):
            print(f"⚠️ Warning: Discarding non-dictionary schema object: {schema}")
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
