"""
Configuration loader for Butler Agent tools.

Loads and validates the unified tools configuration from YAML.
Handles environment variable substitution and provides access to config sections.
"""
import os
import re
import yaml
from pathlib import Path

# Path to the unified configuration file
CONFIG_FILE = Path(__file__).parent.parent / "config" / "tools_config.yaml"

def _process_env_var_references(value):
    """
    Process string values containing ${ENV_VAR} or ${ENV_VAR:default} patterns.
    
    Args:
        value: String potentially containing environment variable references
        
    Returns:
        Processed string with environment variables replaced
    """
    if not isinstance(value, str):
        return value
        
    # Match ${ENV_VAR} or ${ENV_VAR:default}
    pattern = r'\${([A-Za-z0-9_]+)(?::([^}]+))?}'
    
    def replace_env_var(match):
        env_var = match.group(1)
        default = match.group(2) if match.group(2) else None
        
        # Convert string 'true'/'false' to boolean for defaults
        if default == 'true':
            default = True
        elif default == 'false':
            default = False
            
        return os.environ.get(env_var, default)
        
    if re.search(pattern, value):
        # Replace all occurrences of the pattern
        result = re.sub(pattern, lambda m: str(replace_env_var(m)), value)
        
        # Convert 'true'/'false' strings to booleans
        if result.lower() == 'true':
            return True
        elif result.lower() == 'false':
            return False
        return result
            
    return value

def _process_config_item(item):
    """
    Recursively process configuration items, replacing environment variables.
    
    Args:
        item: Configuration item (can be dict, list, or scalar)
        
    Returns:
        Processed configuration with environment variables replaced
    """
    if isinstance(item, dict):
        return {k: _process_config_item(v) for k, v in item.items()}
    elif isinstance(item, list):
        return [_process_config_item(i) for i in item]
    else:
        return _process_env_var_references(item)

def validate_config_schema(config):
    """
    Validate the structure and data types of the configuration.
    
    Args:
        config: The loaded configuration dictionary
        
    Returns:
        bool: True if valid, False if invalid
        
    Raises:
        ValueError: If the configuration schema is invalid
    """
    if not isinstance(config, dict):
        raise ValueError("Configuration must be a dictionary")
    
    # Validate settings section
    if 'settings' in config:
        if not isinstance(config['settings'], dict):
            raise ValueError("'settings' must be a dictionary")
            
        # Check specific settings types
        settings = config['settings']
        if 'include_obsidian_tools' in settings and not isinstance(settings['include_obsidian_tools'], bool):
            raise ValueError("'include_obsidian_tools' must be a boolean")
        if 'use_core_memory' in settings and not isinstance(settings['use_core_memory'], bool):
            raise ValueError("'use_core_memory' must be a boolean")
        if 'use_mcp_tools' in settings and not isinstance(settings['use_mcp_tools'], bool):
            raise ValueError("'use_mcp_tools' must be a boolean")
        if 'use_semantic_search' in settings and not isinstance(settings['use_semantic_search'], bool):
            raise ValueError("'use_semantic_search' must be a boolean")
    
    # Validate tool sections
    for section in ['core_tools', 'obsidian_tools', 'memory_tools', 'fallback_tools', 'community_tools']:
        if section in config:
            if not isinstance(config[section], list):
                raise ValueError(f"'{section}' must be a list")
                
            for i, tool in enumerate(config[section]):
                if not isinstance(tool, dict):
                    raise ValueError(f"Tool at index {i} in '{section}' must be a dictionary")
                if 'name' not in tool:
                    raise ValueError(f"Tool at index {i} in '{section}' must have a 'name' key")
                if 'enabled' in tool and not isinstance(tool['enabled'], bool):
                    raise ValueError(f"'enabled' for tool '{tool['name']}' in '{section}' must be a boolean")
                
                if section == 'community_tools':
                    if 'required_env_vars' in tool and not isinstance(tool['required_env_vars'], list):
                        raise ValueError(f"'required_env_vars' for tool '{tool['name']}' must be a list")
    
    # Validate mcp_servers section
    if 'mcp_servers' in config:
        if not isinstance(config['mcp_servers'], list):
            raise ValueError("'mcp_servers' must be a list")
            
        for i, server in enumerate(config['mcp_servers']):
            if not isinstance(server, dict):
                raise ValueError(f"Server at index {i} must be a dictionary")
            if 'name' not in server:
                raise ValueError(f"Server at index {i} must have a 'name' key")
            if 'url' not in server:
                raise ValueError(f"Server '{server.get('name', f'at index {i}')}' must have a 'url' key")
            if 'transport' not in server:
                raise ValueError(f"Server '{server.get('name', f'at index {i}')}' must have a 'transport' key")
            if 'enabled' in server and not isinstance(server['enabled'], bool):
                raise ValueError(f"'enabled' for server '{server['name']}' must be a boolean")
            if 'required_env_vars' in server and not isinstance(server['required_env_vars'], list):
                raise ValueError(f"'required_env_vars' for server '{server['name']}' must be a list")
                
            # Validate server tools if present
            if 'tools' in server:
                if not isinstance(server['tools'], list):
                    raise ValueError(f"'tools' for server '{server['name']}' must be a list")
                
                for j, tool in enumerate(server['tools']):
                    if not isinstance(tool, dict):
                        raise ValueError(f"Tool at index {j} in server '{server['name']}' must be a dictionary")
                    if 'name' not in tool:
                        raise ValueError(f"Tool at index {j} in server '{server['name']}' must have a 'name' key")
                    if 'enabled' in tool and not isinstance(tool['enabled'], bool):
                        raise ValueError(f"'enabled' for tool '{tool['name']}' in server '{server['name']}' must be a boolean")
    
    return True

def validate_required_env_vars(config):
    """
    Validate that all required environment variables for enabled tools are set.
    
    Args:
        config: Loaded configuration dictionary
        
    Returns:
        List of missing required environment variables
    """
    missing_vars = []
    
    # Check global required env vars
    global_env_vars = config.get('settings', {}).get('env_vars', {})
    if global_env_vars:
        for var, requirement in global_env_vars.items():
            if requirement == 'required' and not os.environ.get(var):
                missing_vars.append(var)
    
    # Check community tools
    for tool in config.get('community_tools', []):
        if tool.get('enabled', False) and 'required_env_vars' in tool:
            for var in tool['required_env_vars']:
                if not os.environ.get(var):
                    missing_vars.append(f"{var} (required by {tool['name']} tool)")
    
    # Check MCP servers
    for server in config.get('mcp_servers', []):
        if server.get('enabled', False) and 'required_env_vars' in server:
            for var in server['required_env_vars']:
                if not os.environ.get(var):
                    missing_vars.append(f"{var} (required by {server['name']} MCP server)")
    
    return missing_vars

def load_config():
    """
    Load and process the configuration file.
    
    Returns:
        dict: Processed configuration dictionary
    """
    try:
        with open(CONFIG_FILE, 'r') as file:
            config = yaml.safe_load(file)
        
        # Validate the configuration schema
        try:
            validate_config_schema(config)
        except ValueError as schema_error:
            print(f"\n⚠️ Configuration Schema Error: {schema_error}")
            return {}
        
        # Process environment variables in the configuration
        processed_config = _process_config_item(config)
        
        # Validate required environment variables for enabled tools
        missing_vars = validate_required_env_vars(processed_config)
        if missing_vars:
            print("\n⚠️ WARNING: Missing required environment variables:")
            for var in missing_vars:
                print(f"  - {var}")
            print("Some features may not work correctly.\n")
        
        return processed_config
    except Exception as e:
        print(f"Error loading configuration: {e}")
        return {}

# Single instance of the configuration
_config_cache = None

def get_config():
    """
    Get the configuration, loading it if necessary.
    
    Returns:
        dict: The configuration dictionary
    """
    global _config_cache
    if _config_cache is None:
        _config_cache = load_config()
    return _config_cache

def get_settings():
    """
    Get the settings section of the configuration.
    
    Returns:
        dict: The settings dictionary
    """
    return get_config().get('settings', {})

def get_enabled_tools_from_section(section_name):
    """
    Get a list of enabled tool configurations from a specific section.
    
    Args:
        section_name: Name of the section to get tools from
        
    Returns:
        list: List of enabled tool configurations
    """
    config = get_config()
    return [tool for tool in config.get(section_name, []) 
            if tool.get('enabled', True)]

def get_tool_names_from_section(section_name):
    """
    Get a set of enabled tool names from a specific section.
    
    Args:
        section_name: Name of the section to get tool names from
        
    Returns:
        set: Set of enabled tool names
    """
    return {tool['name'] for tool in get_enabled_tools_from_section(section_name)}

def get_community_tools_config():
    """
    Get community tools configuration with overrides.
    
    Returns:
        list: List of processed community tool configs with all required data
    """
    return get_enabled_tools_from_section('community_tools')

def get_mcp_servers_config():
    """
    Get MCP servers configuration.
    
    Returns:
        list: List of enabled MCP server configurations
    """
    server_configs = get_enabled_tools_from_section('mcp_servers')
        
    # Ensure server configs are properly formatted for the client
    for config in server_configs:
        # Make sure transport and url are present
        if 'transport' not in config:
            print(f"⚠️ Missing 'transport' in server config: {config}")
        if 'url' not in config:
            print(f"⚠️ Missing 'url' in server config: {config}")
    
    return server_configs
