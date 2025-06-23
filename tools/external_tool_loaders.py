"""
External tool loaders for Butler Agent.

Contains functions to load external tools from community libraries and MCP servers.
"""
from langchain_community import tools as community_tools
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_core.utils.function_calling import convert_to_openai_function

async def load_community_tools(tool_configs):
    """
    Load LangChain community tools based on configuration.
    
    Args:
        tool_configs: List of community tool configurations
        
    Returns:
        tuple: (implementations_dict, schemas_list)
    """
    implementations = {}
    schemas = []
    
    if not tool_configs:
        return implementations, schemas
        
    for tool_config in tool_configs:
        tool_name = tool_config.get('name')
        # Skip if required environment variables are missing
        if 'required_env_vars' in tool_config:
            missing_vars = [var for var in tool_config['required_env_vars'] 
                           if not __import__('os').environ.get(var)]
            if missing_vars:
                print(f"⚠️ Skipping tool '{tool_name}' due to missing environment variables: {missing_vars}")
                continue
                
        # Apply any override configuration
        overrides = tool_config.get('override', {})
        init_args = overrides.get("init_args", {})
        override_name = overrides.get("name")
        override_description = overrides.get("description")
        
        try:
            tool_class = getattr(community_tools, tool_name)
            # Instantiate with overrides if provided
            if init_args:
                tool_instance = tool_class(**init_args)
            else:
                tool_instance = tool_class()
                
            # Apply overrides if provided
            if override_name:
                tool_instance.name = override_name
            if override_description:
                tool_instance.description = override_description
                
            implementations[tool_instance.name] = tool_instance
            schemas.append(convert_to_openai_function(tool_instance))
        except AttributeError:
            print(f"⚠️ Tool '{tool_name}' not found in LangChain community tools")
            continue
        except Exception as e:
            print(f"⚠️ Failed to load community tool '{tool_name}': {e}")
            continue
            
    return implementations, schemas

async def load_mcp_tools(server_configs):
    """
    Load MCP tools from configured servers.
    
    Args:
        server_configs: List of MCP server configurations
        
    Returns:
        tuple: (implementations_dict, schemas_list)
    """
    implementations = {}
    schemas = []
    
    if not server_configs:
        return implementations, schemas
        
    print("\n--- 🔎 Discovering MCP Tools ---")
    
    # Process servers and extract necessary configuration
    processed_servers_dict = {}
    tool_configurations = {}  # Store tool configs by server name
    
    for i, server in enumerate(server_configs):
        # Skip if required environment variables are missing
        if 'required_env_vars' in server:
            missing_vars = [var for var in server['required_env_vars'] 
                           if not __import__('os').environ.get(var)]
            if missing_vars:
                print(f"⚠️ Skipping MCP server '{server.get('name')}' due to missing environment variables: {missing_vars}")
                continue
                
        # Add server configuration - use server name or index as the key
        server_name = server.get('name', f'server_{i}')
        processed_servers_dict[server_name] = {
            'transport': server.get('transport'),
            'url': server.get('url')
        }
        
        # Store tool configurations for this server (only explicitly mentioned tools)
        tool_configurations[server_name] = {tool['name']: tool for tool in server.get('tools', [])}
    
    if not processed_servers_dict:
        return implementations, schemas
        
    try:
        client = MultiServerMCPClient(processed_servers_dict)
        mcp_tools = await client.get_tools()

        for tool in mcp_tools:
            server_name = None
            tool_config = None
            
            for name, configs in tool_configurations.items():
                if tool.name in configs:
                    server_name = name
                    tool_config = configs[tool.name]
                    break
            
            # If tool is explicitly mentioned in config, check if it's disabled
            if tool_config is not None:
                if not tool_config.get('enabled', True):
                    print(f"⚠️ Skipping disabled tool: {tool.name}")
                    continue
                
                # Apply overrides if present
                if 'override' in tool_config:
                    overrides = tool_config['override']
                    tool.name = overrides.get("name", tool.name)
                    tool.description = overrides.get("description", tool.description)
                    if "parameters" in overrides:
                        tool.parameters = overrides["parameters"]
            
            # If tool is not mentioned in config OR is mentioned and enabled, load it
            def create_async_wrapper(t):
                async def async_wrapper(**kwargs):
                    return await t.ainvoke(input=kwargs)
                return async_wrapper
                    
            implementations[tool.name] = create_async_wrapper(tool)
            schemas.append(convert_to_openai_function(tool))
            
    except Exception as e:
        print(f"⚠️ Error in MCP tools: {e}")
        print(f"Server configs type: {type(server_configs)}")
        print(f"Processed servers dict type: {type(processed_servers_dict)}")
        if processed_servers_dict:
            print(f"First server key: {next(iter(processed_servers_dict))}")
            print(f"First server value: {processed_servers_dict[next(iter(processed_servers_dict))]}")
        import traceback
        traceback.print_exc()
            
    return implementations, schemas
