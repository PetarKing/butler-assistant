# This file defines a dictionary of MCP servers that can be connected to.

from config.settings import PIPEDREAM_TAVILY_URL


MCP_SERVERS_TO_CONNECT = {
    # # Example 1: A local calculator tool running over HTTP
    # "calculator": {
    #     "transport": "http",
    #     "url": "http://localhost:8001/mcp"
    # },
    # # Example 2: A more complex tool that is started as a subprocess
    # "corporate_kb": {
    #     "transport": "stdio",
    #     "command": "python -m company_knowledge_base.server"
    # }
    # # Add other servers here...
    "Tavily": {
        "transport": "streamable_http",
        "url": PIPEDREAM_TAVILY_URL,
    }
}

MCP_TOOL_OVERRIDES = {
    "TAVILY-SEND-QUERY": {
        "name": "ai_web_search",
        "description": "Search the web using Tavily AI.",
    }
}
