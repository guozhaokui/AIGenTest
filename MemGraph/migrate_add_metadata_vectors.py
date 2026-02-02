"""
Migration script: Generate vectors for existing metadata N-grams

This script adds vectors for metadata N-grams that were previously skipped.
Run this after updating knowledge_indexer.py to include metadata in vector generation.
"""
import asyncio
import sqlite3
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.config import METADATA_DB_PATH, FAISS_INDEX_PATH
from src.embedding_client import EmbeddingClient
import numpy as np
import faiss


async def migrate_metadata_vectors():
    """Generate vectors for existing metadata N-grams"""

    # Connect to database
    conn = sqlite3.connect(str(METADATA_DB_PATH))

    # Load FAISS index
    if FAISS_INDEX_PATH.exists():
        index = faiss.read_index(str(FAISS_INDEX_PATH))
        print(f"Loaded FAISS index with {index.ntotal} vectors")
    else:
        print("Error: FAISS index not found!")
        return

    # Get all unique metadata N-grams that don't have vectors yet
    cursor = conn.execute('''
        SELECT DISTINCT content, gram_size
        FROM ngrams
        WHERE gram_type = 'metadata'
        AND content NOT IN (SELECT ngram_content FROM ngram_vectors)
        ORDER BY content
    ''')

    metadata_ngrams = cursor.fetchall()
    print(f"Found {len(metadata_ngrams)} metadata N-grams without vectors")

    if not metadata_ngrams:
        print("No migration needed - all metadata N-grams already have vectors")
        conn.close()
        return

    # Initialize embedding client
    embedding_client = EmbeddingClient()

    # Generate vectors for each metadata N-gram
    success_count = 0
    failed_count = 0

    for content, gram_size in metadata_ngrams:
        try:
            # Generate embedding
            embedding = await embedding_client.embed_text(content)

            # Normalize
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm

            # Add to FAISS
            embedding = embedding.reshape(1, -1)
            index.add(embedding)

            faiss_idx = index.ntotal - 1

            # Record to database
            conn.execute('''
                INSERT OR IGNORE INTO ngram_vectors (ngram_content, faiss_idx, gram_size)
                VALUES (?, ?, ?)
            ''', (content, faiss_idx, gram_size))

            success_count += 1

            if success_count % 10 == 0:
                print(f"  Processed {success_count}/{len(metadata_ngrams)}...")
                conn.commit()

        except Exception as e:
            print(f"  Failed to process '{content}': {e}")
            failed_count += 1

    # Final commit
    conn.commit()

    # Save updated FAISS index
    faiss.write_index(index, str(FAISS_INDEX_PATH))
    print(f"Saved updated FAISS index with {index.ntotal} vectors")

    # Close connection
    conn.close()

    print(f"\n=== Migration Complete ===")
    print(f"Successfully added vectors for {success_count} metadata N-grams")
    print(f"Failed: {failed_count}")

    # Show statistics
    conn = sqlite3.connect(str(METADATA_DB_PATH))
    cursor = conn.execute('''
        SELECT gram_type, COUNT(DISTINCT content) as total,
               COUNT(DISTINCT CASE WHEN content IN (SELECT ngram_content FROM ngram_vectors) THEN content END) as with_vectors
        FROM ngrams
        GROUP BY gram_type
        ORDER BY gram_type
    ''')

    print(f"\n=== N-gram Vector Coverage ===")
    for row in cursor.fetchall():
        gram_type, total, with_vectors = row
        percentage = (with_vectors / total * 100) if total > 0 else 0
        print(f"{gram_type:15}: {with_vectors:4}/{total:4} ({percentage:.1f}%)")

    conn.close()


if __name__ == '__main__':
    print("Starting migration to add metadata N-gram vectors...")
    asyncio.run(migrate_metadata_vectors())
