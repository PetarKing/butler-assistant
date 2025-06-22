"""
Obsidian Vault Indexer

This script builds a vector database index of an Obsidian vault for semantic search.
It handles cleanup of existing databases and provides interactive confirmation
for destructive operations.

Usage:
    python build_index.py

The script will:
1. Check for existing ChromaDB database
2. Prompt user for confirmation to delete existing data
3. Initialize embedding service and index the vault
4. Handle errors gracefully with informative messages
"""

import os
import shutil
import sys
from services.embeddings import EmbeddingService
from config.settings import CHROMA_DB_PATH


def confirm_database_deletion() -> bool:
    """
    Prompt user for confirmation to delete existing database.
    
    Returns:
        True if user confirms deletion, False otherwise
        
    Raises:
        SystemExit: If running in non-interactive environment
    """
    try:
        response = input("   Do you want to delete it and re-index? (y/N): ")
        return response.lower() == 'y'
    except (NameError, EOFError):
        print("Non-interactive environment detected. "
              "Please manually delete the ChromaDB folder if you wish to re-index.")
        sys.exit(1)


def cleanup_existing_database() -> None:
    """
    Remove existing ChromaDB database after user confirmation.
    
    Raises:
        SystemExit: If deletion fails or user cancels
    """
    if not os.path.exists(CHROMA_DB_PATH):
        return
        
    print(f"⚠️ Found existing database at '{CHROMA_DB_PATH}'.")
    
    if not confirm_database_deletion():
        print("-> Indexing cancelled by user.")
        sys.exit(0)
    
    print("-> Deleting old database...")
    try:
        shutil.rmtree(CHROMA_DB_PATH)
        print("-> Old database deleted.")
    except OSError as e:
        print("\n--- ERROR: Could not delete the database directory ---")
        print("Please check file permissions or close any programs using this folder.")
        print(f"System Error: {e}")
        sys.exit(1)


def build_index() -> None:
    """
    Initialize embedding service and build the vault index.
    
    Raises:
        SystemExit: If indexing fails
    """
    try:
        service = EmbeddingService()
        service.load()
        service.index_vault()
        print("-> Indexing completed successfully!")
    except Exception as e:
        print("\n--- FATAL ERROR DURING INDEXING ---")
        print(f"Error: {e}")
        sys.exit(1)


def main() -> None:
    """
    Main function to handle the complete indexing process.
    
    Orchestrates database cleanup and index building with proper
    error handling and user feedback.
    """
    print("--- Obsidian Vault Indexer ---")
    
    cleanup_existing_database()
    build_index()


if __name__ == "__main__":
    main()
