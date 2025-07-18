from datetime import datetime
from pathlib import Path

import openai

from config.personality import SUMMARY_SYSTEM_PROMPT
from config.settings import (CHEAP_MODEL, CORE_MEMORY_FILENAME,
                             LOG_SUBDIR, SANDBOX_ROOT,
                             SUMMARY_FOLDER, VAULT_ROOT)


def assert_inside_vault(
    base: Path, target: Path, err: str = "path outside allowed folder"
) -> None:
    """
    Security check to ensure target path is within the allowed base directory.

    Args:
        base: The base directory that should contain the target
        target: The path to validate
        err: Error message if validation fails

    Raises:
        ValueError: If target path is outside the base directory
    """
    try:
        target.relative_to(base)
    except ValueError:
        raise ValueError(err)


def append_note(rel_path: str, content: str) -> str:
    """
    Append markdown content to a file in the Butler's sandbox directory.

    Creates the file and necessary parent directories if they don't exist.

    Args:
        rel_path: Relative path to the file within the sandbox
        content: Markdown content to append

    Returns:
        Success message with the relative path

    Raises:
        ValueError: If the path escapes the sandbox directory
    """
    rel_path = rel_path.lstrip("/\\")
    p = (SANDBOX_ROOT / rel_path).resolve()
    assert_inside_vault(SANDBOX_ROOT, p, "append path escapes sandbox")
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write("\n" + content)
    return f"Appended to {p.relative_to(SANDBOX_ROOT)}"


def read_note(rel_path: str) -> str:
    """
    Read the raw markdown content of a file in the Obsidian vault.

    Args:
        rel_path: Relative path to the file within the vault

    Returns:
        The file content as a string, or an error message if file not found

    Raises:
        ValueError: If the path escapes the vault directory
    """
    p = (VAULT_ROOT / rel_path).expanduser().resolve()
    assert_inside_vault(VAULT_ROOT, p, "read path escapes vault")
    try:
        return p.read_text(encoding="utf-8")
    except FileNotFoundError:
        return f"[read_note-error] File not found: {rel_path}"


def list_vault_files(_: str = "") -> list[str]:
    """
    Get a list of all markdown files in the Obsidian vault.

    Args:
        _: Unused parameter for API consistency

    Returns:
        List of relative paths to all .md files in the vault
    """
    return [str(p.relative_to(VAULT_ROOT)) for p in VAULT_ROOT.rglob("*.md")]


def read_entire_memory(_: str = "") -> str:
    """
    Read and concatenate all session summary files for long-term memory.

    Args:
        _: Unused parameter for API consistency

    Returns:
        Concatenated content of all summary files, or message if none exist
    """
    summary_dir = SANDBOX_ROOT / SUMMARY_FOLDER
    summary_dir.mkdir(parents=True, exist_ok=True)
    mem_files = sorted(summary_dir.glob("*.md"))
    return (
        "\n\n".join(
            f"{{{f.name}}}\n{f.read_text(encoding='utf-8')}" for f in mem_files)
        or "[memory] No summaries yet."
    )


def recent_session_summaries(n: int = 3) -> str:
    """
    Read the most recent session summaries for context.

    Args:
        n: Number of recent summaries to retrieve

    Returns:
        Concatenated content of the n most recent summaries
    """
    summary_dir = SANDBOX_ROOT / SUMMARY_FOLDER
    summary_dir.mkdir(parents=True, exist_ok=True)
    mem_files = sorted(
        summary_dir.glob("*.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:n]
    return "\n\n".join(f.read_text(encoding="utf-8") for f in mem_files)


def save_session_summary(history: list[dict]) -> None:
    """
    Generate and save a summary of the conversation history using AI.

    Processes the conversation history, generates a concise summary using
    the configured AI model, and saves it with a timestamp.

    Args:
        history: List of message dictionaries containing conversation history
    """
    try:
        def role_and_content(msg):
            """Extract role and content from message object or dict."""
            if isinstance(msg, dict):
                return msg.get("role"), msg.get("content", "")
            role = getattr(msg, "role", None)
            content = getattr(msg, "content", "")
            return role, content

        # Build conversation text from history
        parts = []
        for m in history:
            role, content = role_and_content(m)
            if role in ("user", "assistant"):
                parts.append(f"{role}: {content}")

        if not parts:
            return

        # Truncate to prevent token limits
        conversation_text = "\n".join(parts)[-8000:]

        # Generate summary using AI
        summary_resp = openai.chat.completions.create(
            model=CHEAP_MODEL,
            messages=[
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": conversation_text},
            ],
            max_tokens=1000,
            temperature=0.2,
        )

        summary = summary_resp.choices[0].message.content.strip()

        # Save summary with timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
        summary_dir = SANDBOX_ROOT / SUMMARY_FOLDER
        summary_dir.mkdir(parents=True, exist_ok=True)
        fn = summary_dir / f"session-{timestamp}.md"
        fn.write_text(summary, encoding="utf-8")

    except Exception as e:
        print(f"[summary-save-error] {e}")


def append_core_memory(content: str) -> str:
    """
    Add new information to the agent's persistent core memory.

    Appends timestamped content to the core memory file, which contains
    key facts and standing instructions that persist across sessions.

    Args:
        content: Information to add to core memory

    Returns:
        Success message from the append operation
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_content = f"**{timestamp}**\n{content.strip()}\n\n---\n"
    return append_note(rel_path=CORE_MEMORY_FILENAME, content=formatted_content)


def sandbox_files(max_summaries: int = None) -> list[str]:
    """
    List all markdown files in the Butler's sandbox directory.
    
    Core memory file (`CORE_MEMORY_FILENAME`) and files in log directory are excluded.
    Summary files can be limited by the max_summaries parameter.

    Args:
        max_summaries: Optional limit to the number of recent summary files to include.
                      If None, includes all summary files.

    Returns:
        List of relative paths to markdown files in the sandbox
    """
    filtered_paths = []
    summary_dir = SANDBOX_ROOT / SUMMARY_FOLDER
    
    for p in SANDBOX_ROOT.rglob("*.md"):
        # Skip non-markdown files
        if not p.is_file() or p.suffix.lower() != ".md":
            continue
            
        # Check if path is in log subdirectory
        try:
            p.relative_to(LOG_SUBDIR)
            continue  # Skip files in log directory
        except ValueError:
            pass
            
        # Check if file is the core memory file
        if p.name == CORE_MEMORY_FILENAME:
            continue
            
        # Check if file is in summaries directory - handle these separately
        try:
            p.relative_to(summary_dir)
            continue
        except ValueError:
            # Not a summary file, add to regular files
            filtered_paths.append(str(p.relative_to(SANDBOX_ROOT)))
            
    if max_summaries is not None:
        # Get only the N most recent summary files
        summary_files = sorted(
            summary_dir.glob("*.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )[:max_summaries]
    else:
        # Get all summary files
        summary_files = summary_dir.glob("*.md")
        
    # Add summary files to the result
    for p in summary_files:
        filtered_paths.append(str(p.relative_to(SANDBOX_ROOT)))
    
    return filtered_paths
