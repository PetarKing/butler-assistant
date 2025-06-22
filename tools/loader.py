"""Simple tool loader to consolidate the messy conditional logic."""
from .registry import (
    CORE_TOOL_IMPLEMENTATIONS, CORE_TOOL_SCHEMAS,
    OBSIDIAN_TOOL_IMPLEMENTATIONS, OBSIDIAN_TOOL_SCHEMAS,
    OBSIDIAN_FALLBACK_IMPLEMENTATIONS, OBSIDIAN_FALLBACK_SCHEMAS,
    CORE_MEMORY_TOOL_IMPLEMENTATION, CORE_MEMORY_TOOL_SCHEMA,
    get_rag_tools, compute_community_tools, compute_mcp_tools
)

# --- Import settings ---
from config.settings import INCLUDE_OBSIDIAN_TOOLS, USE_CORE_MEMORY, USE_MCP_TOOLS

async def initialize_app_tools(rag_service):
    """
    Initialize application tools based on configuration settings and return
    a tuple of (tool_implementations, tool_schemas).
    """
    print("\n--- 🛠️  Tools made Available ---")

    # 1. Start with core tools
    final_implementations = dict(CORE_TOOL_IMPLEMENTATIONS)
    final_schemas = list(CORE_TOOL_SCHEMAS)

    # 2. Add community tools
    comm_implementations, comm_schemas = compute_community_tools()

    final_implementations.update(comm_implementations)
    final_schemas.extend(comm_schemas)

    # 3. Conditionally add MCP tools
    if USE_MCP_TOOLS:
        try:
            mcp_implementations, mcp_schemas = await compute_mcp_tools()
            final_implementations.update(mcp_implementations)
            final_schemas.extend(mcp_schemas)
            print(f"🧰 Following MCP tools are available: {list(mcp_implementations.keys())}")
        except Exception as e:
            print(f"⚠️ Could not initialize MCP tools: {e}")

    # 4. Conditionally add Obsidian-related tools
    if INCLUDE_OBSIDIAN_TOOLS:
        final_implementations.update(OBSIDIAN_TOOL_IMPLEMENTATIONS)
        final_schemas.extend(OBSIDIAN_TOOL_SCHEMAS)

        if USE_CORE_MEMORY:
            # Make sure to import these new variables from tools/base.py
            final_implementations.update(CORE_MEMORY_TOOL_IMPLEMENTATION)
            final_schemas.append(CORE_MEMORY_TOOL_SCHEMA)

        # 3a. Add RAG tools OR the fallback tools
        if rag_service:
            try:
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
