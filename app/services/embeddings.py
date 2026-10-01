import os
import json
import sqlite3
import numpy as np
from typing import List
from google import genai

CACHE_DB_PATH = os.path.join(os.path.dirname(__file__), "embeddings.db")

def _init_db():
    with sqlite3.connect(CACHE_DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS embeddings (
                text TEXT PRIMARY KEY,
                embedding JSON
            )
        ''')

_init_db()

_client = None

def _get_client():
    global _client
    if _client is None:
        try:
            _client = genai.Client()
        except Exception:
            pass
    return _client

def get_embedding(text: str) -> List[float]:
    if not text:
        return []
        
    with sqlite3.connect(CACHE_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT embedding FROM embeddings WHERE text = ?", (text,))
        row = cursor.fetchone()
        if row:
            return json.loads(row[0])
            
    client = _get_client()
    if not client:
        return []
        
    try:
        response = client.models.embed_content(
            model='models/text-embedding-004',
            contents=text
        )
        embedding = response.embeddings[0].values
    except Exception:
        return []
    
    with sqlite3.connect(CACHE_DB_PATH) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO embeddings (text, embedding) VALUES (?, ?)",
            (text, json.dumps(embedding))
        )
    return embedding

def cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b:
        return 0.0
    a_arr = np.array(a)
    b_arr = np.array(b)
    norm_a = np.linalg.norm(a_arr)
    norm_b = np.linalg.norm(b_arr)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a_arr, b_arr) / (norm_a * norm_b))
