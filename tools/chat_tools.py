def reset_chat(_: str = "") -> str:
    """
    Reset the assistant's conversation history.

    Clears the current conversation context, allowing for a fresh start
    while maintaining the assistant's core personality and settings.

    Args:
        _: Unused parameter (tool takes no meaningful input)

    Returns:
        Confirmation message
    """
    return "Chat has been reset."


def quit_chat(_: str = "") -> str:
    """
    Signal the voice chat system to exit gracefully.

    Triggers the main chat loop to terminate, allowing for proper cleanup
    and shutdown procedures.

    Args:
        _: Unused parameter (tool takes no meaningful input)

    Returns:
        Exit confirmation message
    """
    return "Exiting chat."


def enable_high_brain_power(_: str = "") -> str:
    """
    Switch to the high-performance AI model for complex tasks.

    Enables the most capable model (typically o3) for the remainder of
    the current chat session. Use for complex reasoning or analysis.

    Args:
        _: Unused parameter (tool takes no meaningful input)

    Returns:
        Mode activation confirmation
    """
    return "High-brain-power mode enabled."


def enable_private_mode(_: str = "") -> str:
    """
    Enable private conversation mode.

    Marks the current conversation as private, preventing the creation
    of Butler Log entries when the chat session ends.

    Args:
        _: Unused parameter (tool takes no meaningful input)

    Returns:
        Privacy mode confirmation
    """
    return "Private conversation mode enabled. I will not write a Butler Log for this chat."
