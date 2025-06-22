import json

def build_semantic_search(rag_service) -> callable:
    """
    Build a semantic search tool using the provided RAG service.
    
    Creates a function that performs semantic searches across the entire
    Obsidian vault using vector embeddings for relevance matching.
    
    Args:
        rag_service: Initialized RAG service with embedding capabilities
        
    Returns:
        Callable function that performs semantic searches
    """
    def semantic_search(query: str, use_compression: bool = False) -> str:
        """
        Perform a semantic search across the Obsidian vault.
        
        Args:
            query: Search query string
            use_compression: Whether to return compressed/summarized results
            
        Returns:
            JSON string containing search results with relevance scores
        """
        results = rag_service.search(query, use_compression)
        return json.dumps(results, indent=2)
    
    return semantic_search

def build_filtered_semantic_search(rag_service) -> callable:
    """
    Build a tag-filtered semantic search tool using the provided RAG service.
    
    Creates a function that performs semantic searches but limits results
    to notes containing specific tags.
    
    Args:
        rag_service: Initialized RAG service with tag filtering capabilities
        
    Returns:
        Callable function that performs filtered semantic searches
    """
    def filtered_search(query: str, tag: str) -> str:
        """
        Perform a semantic search filtered by tag.
        
        Args:
            query: Search query string
            tag: Tag to filter by (without '#' prefix)
            
        Returns:
            JSON string containing filtered search results
        """
        results = rag_service.search_with_tag_filter(query, tag)
        return json.dumps(results, indent=2)
    
    return filtered_search
