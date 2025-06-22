import fnmatch
import os
import re
import time

from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import LLMChainExtractor
from langchain_chroma import Chroma
from langchain_community.document_loaders import ObsidianLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
from tqdm import tqdm

from config.settings import (CHEAP_MODEL, CHROMA_DB_PATH, EMBEDDING_MODEL_NAME,
                             SEMANTIC_SEARCH_K_VALUE, TOOL_CALL_FILE_NAME,
                             VAULT_ROOT)


class EmbeddingService:
    """
    Manages semantic search capabilities for an Obsidian vault using ChromaDB.

    Provides functionality to:
    - Index Obsidian vault documents with embeddings
    - Perform semantic search across the knowledge base
    - Filter search results by tags
    - Use contextual compression for improved results
    """

    def __init__(self):
        """Initialize the service with deferred loading for performance."""
        self.vault_path = VAULT_ROOT
        self.db_path = CHROMA_DB_PATH

        # Defer heavy initialization until load() is called
        self.embeddings = None
        self.vector_store = None
        self.retriever = None
        self.compression_retriever = None

    def load(self) -> None:
        """
        Initialize embeddings model, vector store, and retrievers.

        Must be called before using search functionality. Loads the existing
        ChromaDB index if available, otherwise prints a warning.
        """
        self.embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL_NAME)

        if os.path.exists(self.db_path):
            try:
                self.vector_store = Chroma(
                    persist_directory=self.db_path,
                    embedding_function=self.embeddings,
                )
                self._initialize_retrievers()
                print("✅ Embedding service loaded successfully.")
            except Exception as e:
                print(
                    f"⚠️ Error loading RAG index. Run 'build_index.py' to rebuild. Error: {e}"
                )
        else:
            print(
                f"⚠️ Database path '{self.db_path}' not found. Run 'build_index.py' to create it."
            )

    def _initialize_retrievers(self) -> None:
        """Initialize semantic search retrievers with MMR and compression."""
        if not self.vector_store:
            return

        # MMR retriever for diverse results
        self.retriever = self.vector_store.as_retriever(
            search_type="mmr",
            search_kwargs={"k": SEMANTIC_SEARCH_K_VALUE, "fetch_k": 20},
        )

        # Contextual compression retriever for refined results
        llm_compressor = ChatOpenAI(temperature=0, model=CHEAP_MODEL)
        compressor = LLMChainExtractor.from_llm(llm_compressor)
        self.compression_retriever = ContextualCompressionRetriever(
            base_compressor=compressor, base_retriever=self.retriever
        )

    def _load_and_process_documents(self) -> list:
        """
        Load documents from vault and process metadata for embedding.

        Returns:
            List of processed document chunks ready for embedding

        Raises:
            RuntimeError: If document processing fails
        """
        print("\nStep 1: Loading notes from Obsidian vault...")

        # Exclude files that shouldn't be embedded
        exclude_patterns = [f"**/{TOOL_CALL_FILE_NAME}",
                            "*/.trash/*"]
        print(f"-> Excluding {len(exclude_patterns)} file patterns.")

        loader = ObsidianLoader(self.vault_path)
        docs = loader.load()
        print(f"-> Loaded {len(docs)} documents.")

        # Process metadata for each document
        processed_docs = []
        for doc in docs:
            try:
                path = doc.metadata.get("path")

                # Skip excluded files
                if any(fnmatch.fnmatch(path, pattern) for pattern in exclude_patterns):
                    continue

                # Add relative path metadata
                note_realpath = os.path.realpath(doc.metadata["path"])
                vault_realpath = os.path.realpath(self.vault_path)
                prefix_to_remove = vault_realpath + os.sep

                if note_realpath.startswith(prefix_to_remove):
                    doc.metadata["relative_path"] = note_realpath[
                        len(prefix_to_remove):
                    ]
                else:
                    raise ValueError(
                        f"Note path '{note_realpath}' not inside vault root '{vault_realpath}'."
                    )

                # Extract and add tags
                tags = re.findall(r"#([\w/-]+)", doc.page_content)
                if tags:
                    for t in tags:
                        doc.metadata[f"tag__{t}"] = True

                processed_docs.append(doc)

            except Exception as e:
                raise RuntimeError(
                    f"Failed to process document '{doc.metadata.get('path')}': {e}"
                )

        print(f"-> Processed {len(processed_docs)} documents.")

        # Split documents into chunks for better embedding
        print("Step 2: Splitting documents into chunks...")
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500, chunk_overlap=200
        )
        chunked_docs = text_splitter.split_documents(processed_docs)
        print(f"-> Created {len(chunked_docs)} chunks.")

        return chunked_docs

    def index_vault(self) -> None:
        """
        Build the ChromaDB index from vault documents.

        Processes all documents in the vault, creates embeddings, and stores
        them in ChromaDB for semantic search. This operation can take several
        minutes depending on vault size.
        """
        if not self.embeddings:
            self.embeddings = HuggingFaceEmbeddings(
                model_name=EMBEDDING_MODEL_NAME)

        chunked_docs = self._load_and_process_documents()

        print("\nStep 3: Creating embeddings and building index...")

        self.vector_store = Chroma(
            persist_directory=self.db_path, embedding_function=self.embeddings
        )

        start_time = time.time()

        # Process documents in batches with progress bar
        batch_size = 32
        for i in tqdm(
            range(0, len(chunked_docs), batch_size), desc="Embedding documents"
        ):
            batch = chunked_docs[i: i + batch_size]
            self.vector_store.add_documents(documents=batch)

        elapsed_time = time.time() - start_time
        print(f"\n✅ Indexing complete in {elapsed_time:.2f} seconds!")
        print(f"Vector store saved to '{self.db_path}'.")

    def _format_results(self, results) -> list[dict]:
        """
        Format search results for consistent API response.

        Args:
            results: Raw search results from retriever

        Returns:
            List of formatted result dictionaries with deduplicated paths
        """
        formatted_results = []
        seen_paths = set()

        for doc in results:
            relative_path = doc.metadata.get("relative_path")
            if relative_path and relative_path not in seen_paths:
                tag_list = [
                    key[len("tag__"):]
                    for key, val in doc.metadata.items()
                    if key.startswith("tag__") and val is True
                ]
                formatted_results.append(
                    {
                        "relative_path": relative_path,
                        "content_snippet": doc.page_content,
                        "tags": ",".join(tag_list) or "None",
                    }
                )
                seen_paths.add(relative_path)

        return formatted_results

    def search(self, query: str, use_compression: bool = False) -> list[dict]:
        """
        Perform semantic search across the indexed vault.

        Args:
            query: Search query text
            use_compression: Whether to use contextual compression for results

        Returns:
            List of search results with document snippets and metadata
        """
        if not self.retriever:
            return [{"error": "RAG service not initialized."}]

        if use_compression and self.compression_retriever:
            results = self.compression_retriever.invoke(query)
        else:
            results = self.retriever.invoke(query)

        return self._format_results(results)

    def search_with_tag_filter(self, query: str, tag: str) -> list[dict]:
        """
        Perform semantic search filtered by specific tags.

        Args:
            query: Search query text
            tag: Tag to filter results by

        Returns:
            List of search results containing the specified tag
        """
        if not self.vector_store:
            return [{"error": "RAG service not initialized."}]

        results = self.vector_store.similarity_search(
            query, k=SEMANTIC_SEARCH_K_VALUE, filter= {
                f"tag__{tag}": { "$eq": True }
            }
        )
        return self._format_results(results)
