"""
Phase 1: Vector Embeddings for Accident Pattern Matching

Uses sentence-transformers to embed CRS accident narratives into 384-dim vectors.
Enables semantic similarity search for AlertGenerator reasoning chains.

Usage:
    from backend.ml.embeddings import AccidentEmbeddingGenerator
    
    gen = AccidentEmbeddingGenerator()
    embeddings_cache = gen.batch_embed_from_corpus()
    
    # Find similar accidents
    matches = gen.similarity_search_by_narrative(query_text, top_k=3, threshold=0.65)
    for acc_id, similarity, metadata in matches:
        print(f"{acc_id}: {similarity:.1%} similar")
"""

import logging
import numpy as np
from typing import List, Dict, Tuple, Optional
from pathlib import Path
import sys
import json

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.data.crs_parser import CRSParser

logger = logging.getLogger(__name__)


class AccidentEmbeddingGenerator:
    """Generate and manage embeddings for accident narratives"""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize embedding generator.
        
        Args:
            model_name: HuggingFace model ID for sentence-transformers
                        all-MiniLM-L6-v2: 384-dim, 6M params, fast, good semantic quality
        """
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "sentence-transformers not installed. "
                "Run: pip install sentence-transformers"
            )
        
        logger.info(f"Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.model_name = model_name
        self.embedding_dim = 384  # all-MiniLM output dimension
        
        # In-memory cache (in production: PostgreSQL database)
        self.embedding_cache = {}  # {accident_id: {embedding, narrative, metadata}}
        
        logger.info(f"✓ Model loaded. Embedding dimension: {self.embedding_dim}")
    
    def generate_embeddings(self, texts: List[str], batch_size: int = 100) -> np.ndarray:
        """
        Encode list of texts into vector embeddings.
        
        Args:
            texts: List of narrative texts to embed
            batch_size: Process in batches for memory efficiency
            
        Returns:
            numpy array of shape (len(texts), 384)
        """
        logger.info(f"Encoding {len(texts)} texts with batch_size={batch_size}")
        
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=True,
            convert_to_numpy=True,
            normalize_embeddings=True  # L2 normalization for cosine similarity
        )
        
        logger.info(f"✓ Generated embeddings: shape {embeddings.shape}")
        return embeddings
    
    def batch_embed_from_corpus(self) -> Dict[str, Dict]:
        """
        Embed all CRS accident narratives.
        
        Returns:
            Dict of {accident_id: {embedding (np.array), narrative (str), metadata (dict)}}
        """
        parser = CRSParser()
        corpus = parser.get_corpus()
        
        logger.info(f"Processing {len(corpus)} accidents from CRS corpus")
        
        # Extract narratives and metadata
        narratives = []
        accident_meta = {}
        
        for acc in corpus:
            narratives.append(acc.narrative_text)
            accident_meta[acc.accident_id] = {
                'date': acc.date,
                'station': acc.station,
                'deaths': acc.deaths,
                'delay_before_accident_minutes': acc.delay_before_accident_minutes,
                'root_cause': acc.root_cause,
                'signal_state': acc.signal_state,
                'track_state': acc.track_state,
                'maintenance_active': acc.maintenance_active
            }
        
        # Generate embeddings
        embeddings = self.generate_embeddings(narratives)
        
        # Cache results
        for i, acc in enumerate(corpus):
            self.embedding_cache[acc.accident_id] = {
                'embedding': embeddings[i],
                'narrative': acc.narrative_text,
                'metadata': accident_meta[acc.accident_id]
            }
        
        logger.info(f"✓ Cached {len(self.embedding_cache)} embeddings in memory")
        return self.embedding_cache
    
    def similarity_search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 3,
        threshold: float = 0.65
    ) -> List[Tuple[str, float, Dict]]:
        """
        Find similar embeddings using cosine similarity.
        
        Args:
            query_embedding: Query vector (384,)
            top_k: Return top K matches
            threshold: Minimum similarity score (0-1)
            
        Returns:
            List of (accident_id, similarity_score, metadata)
        """
        if not self.embedding_cache:
            logger.warning("Embedding cache empty. Call batch_embed_from_corpus() first.")
            return []
        
        # Ensure query is L2 normalized
        query_norm = np.linalg.norm(query_embedding)
        if query_norm > 1e-8:
            query_embedding = query_embedding / query_norm
        
        # Compute cosine similarities
        similarities = []
        for acc_id, data in self.embedding_cache.items():
            sim = np.dot(query_embedding, data['embedding'])  # cosine similarity
            
            if sim >= threshold:
                similarities.append((acc_id, float(sim), data['metadata']))
        
        # Sort by similarity descending
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        results = similarities[:top_k]
        logger.info(f"Found {len(results)} matches (threshold={threshold})")
        
        return results
    
    def similarity_search_by_narrative(
        self,
        query_narrative: str,
        top_k: int = 3,
        threshold: float = 0.65
    ) -> List[Tuple[str, float, Dict]]:
        """
        Find similar accidents by narrative text.
        
        Args:
            query_narrative: Query text (e.g., current junction state description)
            top_k: Return top K matches
            threshold: Minimum similarity (0-1)
            
        Returns:
            List of (accident_id, similarity_score, metadata)
        """
        # Embed query
        query_embedding = self.generate_embeddings([query_narrative])[0]
        
        # Search cache
        return self.similarity_search(query_embedding, top_k, threshold)
    
    def export_embeddings_to_json(self, output_path: str) -> None:
        """
        Export embeddings to JSON for database migration or inspection.
        
        Args:
            output_path: File path to save JSON
        """
        export_data = {}
        
        for acc_id, data in self.embedding_cache.items():
            export_data[acc_id] = {
                'embedding': data['embedding'].tolist(),  # Convert numpy to list
                'narrative_preview': data['narrative'][:200],
                'metadata': data['metadata']
            }
        
        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        logger.info(f"✓ Exported embeddings to: {output_path}")
    
    def get_embedding_stats(self) -> Dict:
        """
        Get statistics about cached embeddings.
        
        Returns:
            Dict with count, dimension, similarity statistics
        """
        if not self.embedding_cache:
            return {'status': 'empty'}
        
        embeddings = np.array([d['embedding'] for d in self.embedding_cache.values()])
        
        # Compute pairwise similarities for statistics
        similarities = []
        for i in range(len(embeddings)):
            for j in range(i + 1, len(embeddings)):
                sim = np.dot(embeddings[i], embeddings[j])
                similarities.append(sim)
        
        return {
            'count': len(self.embedding_cache),
            'dimension': self.embedding_dim,
            'model': self.model_name,
            'mean_similarity': float(np.mean(similarities)) if similarities else 0,
            'min_similarity': float(np.min(similarities)) if similarities else 0,
            'max_similarity': float(np.max(similarities)) if similarities else 0,
            'pairwise_samples': len(similarities)
        }


def main():
    """Development/testing"""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    logger.info("\n" + "="*60)
    logger.info("PHASE 1: ACCIDENT EMBEDDING GENERATION")
    logger.info("="*60)
    
    # Initialize generator
    gen = AccidentEmbeddingGenerator()
    
    # Embed all accidents from CRS corpus
    logger.info("\nStep 1: Embedding all CRS accidents...")
    embeddings_cache = gen.batch_embed_from_corpus()
    
    # Print statistics
    logger.info("\nStep 2: Embedding statistics...")
    stats = gen.get_embedding_stats()
    print("\n=== Embedding Statistics ===")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # Test similarity search
    logger.info("\nStep 3: Testing similarity search...")
    print("\n=== Similarity Search Test ===")
    
    # Use first accident as query
    first_acc_id = list(embeddings_cache.keys())[0]
    query_embedding = embeddings_cache[first_acc_id]['embedding']
    
    logger.info(f"Query accident: {first_acc_id}")
    matches = gen.similarity_search(query_embedding, top_k=3, threshold=0.6)
    
    print(f"\nMatches for {first_acc_id}:")
    for i, (acc_id, sim, metadata) in enumerate(matches, 1):
        print(f"  {i}. {acc_id}: {sim:.1%} similarity")
        print(f"     Station: {metadata['station']}, Deaths: {metadata['deaths']}, Date: {metadata['date']}")
    
    # Export to JSON
    logger.info("\nStep 4: Exporting embeddings to JSON...")
    output_path = "backend/ml/embeddings_export.json"
    gen.export_embeddings_to_json(output_path)
    
    logger.info("\n" + "="*60)
    logger.info("✓ PHASE 1: SUCCESS")
    logger.info("  - Generated embeddings for all CRS accidents")
    logger.info("  - Similarity search functional (cosine distance)")
    logger.info("  - Ready for AlertGenerator integration")
    logger.info("="*60 + "\n")


if __name__ == "__main__":
    main()
