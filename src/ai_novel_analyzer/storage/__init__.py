"""Storage Abstraction Layer - Vector, Structured, and JSON Storage"""

from pathlib import Path
from typing import Dict, Any, Optional, List
import json
import logging
import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)


class JsonFileStore:
    """Simple JSON file-based storage for processed chapters"""
    
    def __init__(self, base_dir: Path):
        """Initialize JSON store
        
        Args:
            base_dir: Base directory to store JSON files
        """
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (self.base_dir / "processed").mkdir(exist_ok=True)
        (self.base_dir / "index").mkdir(exist_ok=True)
        
        logger.info(f"JSON Store initialized at {base_dir}")
    
    def save_chapter(
        self, 
        chapter_id: str,
        data: Dict[str, Any]
    ) -> Path:
        """Save a single chapter's analysis result as JSON file
        
        Args:
            chapter_id: Chapter identifier (e.g., vol_1_chap_01)
            data: Chapter analysis data
            
        Returns:
            Path to saved JSON file
        """
        filepath = self.base_dir / "processed" / f"{chapter_id}.json"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.debug(f"Saved chapter {chapter_id} to {filepath}")
        return filepath
    
    def load_chapter(self, chapter_id: str) -> Optional[Dict[str, Any]]:
        """Load a chapter's analysis result from JSON file
        
        Args:
            chapter_id: Chapter identifier
            
        Returns:
            Chapter data or None if not found
        """
        filepath = self.base_dir / "processed" / f"{chapter_id}.json"
        
        if not filepath.exists():
            return None
        
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def save_index(self, index_name: str, data: Dict[str, Any]) -> Path:
        """Save an index file
        
        Args:
            index_name: Index name (e.g., 'character', 'item', 'event')
            data: Index data
            
        Returns:
            Path to saved index file
        """
        filepath = self.base_dir / "index" / f"{index_name}_index.json"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return filepath
    
    def load_index(self, index_name: str) -> Optional[Dict[str, Any]]:
        """Load an index file
        
        Args:
            index_name: Index name
            
        Returns:
            Index data or None if not found
        """
        filepath = self.base_dir / "index" / f"{index_name}_index.json"
        
        if not filepath.exists():
            return None
        
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)


class VectorStoreManager:
    """Vector database management using ChromaDB"""
    
    def __init__(
        self,
        db_path: Path,
        use_cloud_embeddings: bool = True,
        embedding_api_key: Optional[str] = None,
        embedding_base_url: str = "https://api.siliconflow.cn/v1",
        embedding_model: str = "BAAI/bge-m3"
    ):
        """Initialize vector store
        
        Args:
            db_path: Path to ChromaDB persistent storage
            use_cloud_embeddings: Whether to use cloud API for embeddings
            embedding_api_key: API key for cloud embedding service (if applicable)
            embedding_base_url: OpenAI-compatible embedding API endpoint
            embedding_model: Embedding model name (default: BAAI/bge-m3)
        """
        self.db_path = db_path
        self.use_cloud_embeddings = use_cloud_embeddings
        self.embedding_api_key = embedding_api_key
        self.embedding_base_url = embedding_base_url.rstrip('/')
        self.embedding_model = embedding_model
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=str(db_path),
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Create collection
        self.collection = self.client.create_collection(
            name="novel_analysis",
            metadata={"description": "Novel analysis vector storage"}
        )
        
        logger.info(f"Vector Store initialized at {db_path}")
    
    def add_chunk(
        self,
        chunk_text: str,
        metadata: Dict[str, Any],
        chunk_id: str
    ) -> bool:
        """Add a text chunk with embedding
        
        Args:
            chunk_text: Text content to embed
            metadata: Metadata dict with chapter info, etc.
            chunk_id: Unique identifier for this chunk
            
        Returns:
            True if successful
        """
        
        try:
            # Generate embedding
            embedding = self._generate_embedding(chunk_text)
            
            # Add to ChromaDB
            self.collection.add(
                embeddings=[embedding],
                documents=[chunk_text],
                metadatas=[metadata],
                ids=[chunk_id]
            )
            
            logger.debug(f"Added chunk {chunk_id} to vector store")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add chunk {chunk_id}: {str(e)}")
            return False
    
    def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text
        
        Args:
            text: Input text
            
        Returns:
            Embedding vector (list of floats)
        """
        
        if self.use_cloud_embeddings:
            # Use SiliconFlow Embeddings API via OpenAI-compatible HTTP endpoint
            # (SiliconFlow 没有官方 Python SDK，直接调用 REST API)
            import requests
            
            if not self.embedding_api_key:
                raise RuntimeError(
                    "Embedding API key not configured. "
                    "Set SILICONFLOW_API_KEY in .env file"
                )
            
            response = requests.post(
                f"{self.embedding_base_url}/embeddings",
                headers={
                    "Authorization": f"Bearer {self.embedding_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.embedding_model,
                    "input": [text]
                },
                timeout=60
            )
            
            if response.status_code != 200:
                raise RuntimeError(
                    f"Embedding API request failed: HTTP {response.status_code} - {response.text[:200]}"
                )
            
            data = response.json()
            return data["data"][0]["embedding"]
        else:
            # TODO: Add local embedding model support if needed
            raise NotImplementedError("Local embeddings not yet implemented")
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar chunks
        
        Args:
            query: Search query text
            top_k: Number of results to return
            filters: Optional metadata filters
            
        Returns:
            List of matching chunks with metadata
        """
        
        try:
            query_embedding = self._generate_embedding(query)
            
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=filters,
                include=['documents', 'metadatas', 'distances']
            )
            
            # Format results
            formatted_results = []
            for i in range(len(results['ids'][0])):
                formatted_results.append({
                    'id': results['ids'][0][i],
                    'document': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i],
                    'distance': results['distances'][0][i]
                })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Search failed: {str(e)}")
            return []


class StorageManager:
    """Unified storage manager coordinating all storage backends"""
    
    def __init__(
        self,
        data_dir: Path,
        vector_db_path: Optional[Path] = None,
        use_cloud_embeddings: bool = True,
        embedding_api_key: Optional[str] = None
    ):
        """Initialize unified storage manager
        
        Args:
            data_dir: Base directory for all data
            vector_db_path: Path to ChromaDB storage (optional)
            use_cloud_embeddings: Whether to use cloud embeddings
            embedding_api_key: API key for embedding service
        """
        self.data_dir = data_dir
        self.json_store = JsonFileStore(data_dir)
        
        self.vector_store = None
        if vector_db_path:
            self.vector_store = VectorStoreManager(
                db_path=vector_db_path,
                use_cloud_embeddings=use_cloud_embeddings,
                embedding_api_key=embedding_api_key
            )
        
        logger.info("Storage Manager initialized")
    
    def save_chapter_result(
        self, 
        chapter_id: str,
        result_data: Dict[str, Any]
    ) -> None:
        """Save complete chapter processing result
        
        Args:
            chapter_id: Chapter identifier
            result_data: Complete processing result including structured data
        """
        
        # Save to JSON files
        self.json_store.save_chapter(chapter_id, result_data)
        
        # If vector store is available, also store key information
        if self.vector_store:
            self._store_vector_representations(chapter_id, result_data)
    
    def _store_vector_representations(
        self,
        chapter_id: str,
        result_data: Dict[str, Any]
    ) -> None:
        """Store various representations as vectors
        
        This creates multiple vector entries for different aspects of the chapter:
        - Original text chunks
        - Summary text
        - Key structured fields (characters, events, plot_secrets)
        """
        
        # 1. Store original text in smaller chunks
        text_chunks = self._split_text_for_vectors(result_data.get('original_text', ''))
        for i, chunk in enumerate(text_chunks):
            chunk_id = f"{chapter_id}_orig_{i}"
            metadata = {
                'chapter_id': chapter_id,
                'chunk_type': 'original_text',
                'chunk_index': i
            }
            self.vector_store.add_chunk(chunk, metadata, chunk_id)
        
        # 2. Store summary
        if chapter_summary := result_data.get('chapter_summary'):
            summary_text = chapter_summary.get('brief_summary', '')
            if summary_text:
                chunk_id = f"{chapter_id}_summary"
                metadata = {
                    'chapter_id': chapter_id,
                    'chunk_type': 'chapter_summary'
                }
                self.vector_store.add_chunk(summary_text, metadata, chunk_id)
        
        # 3. Store important structured data
        self._store_structured_as_vectors(chapter_id, result_data)
    
    def _split_text_for_vectors(
        self,
        text: str,
        chunk_size: int = 500,
        overlap: int = 50
    ) -> List[str]:
        """Split text into overlapping chunks for better retrieval
        
        Args:
            text: Input text
            chunk_size: Size of each chunk
            overlap: Overlap between chunks
            
        Returns:
            List of text chunks
        """
        import re
        
        # Simple character-based splitting
        chunks = []
        start = 0
        
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start = end - overlap
        
        return chunks
    
    def _store_structured_as_vectors(
        self,
        chapter_id: str,
        result_data: Dict[str, Any]
    ) -> None:
        """Store key structured fields as searchable vectors"""
        
        # Store plot_secrets clues (very searchable)
        if plot_secrets := result_data.get('plot_secrets', {}):
            if clues := plot_secrets.get('clues', []):
                for i, item in enumerate(clues):
                    clue_text = item.get('description', '')
                    if clue_text:
                        chunk_id = f"{chapter_id}_clue_{i}"
                        metadata = {
                            'chapter_id': chapter_id,
                            'chunk_type': 'plot_clue',
                            'clue_index': i,
                            'urgency': item.get('urgency', '中'),
                            'confidence': item.get('confidence', 0.0)
                        }
                        self.vector_store.add_chunk(clue_text, metadata, chunk_id)
        
        # Store character relationships
        if characters := result_data.get('characters', []):
            for char in characters:
                # Combine important relationship info into searchable text
                relation_texts = []
                trust_levels = []
                for rel in char.get('relationships', []):
                    highlights = rel.get('highlights', [])
                    if highlights:
                        relation_texts.append(" ".join(highlights))
                    if rel.get('trust') is not None:
                        trust_levels.append(rel['trust'])
                
                relation_text = " ".join(relation_texts)
                if relation_text:
                    char_name = char.get('name', 'unknown')
                    chunk_id = f"{chapter_id}_char_rel_{char_name}"
                    metadata = {
                        'chapter_id': chapter_id,
                        'chunk_type': 'character_relationship',
                        'character_name': char_name,
                        'trust_level': max(trust_levels) if trust_levels else 0
                    }
                    self.vector_store.add_chunk(relation_text, metadata, chunk_id)
