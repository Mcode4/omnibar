import os
import sqlite3
from datetime import datetime, timedelta
import numpy as np


class UserDatabase:
    def __init__(self, db_path=None):
        db_path = db_path or os.path.expanduser("~/.local/share/omnimanager/user.db")
        self.APP_DIR = os.path.dirname(db_path)
        self.USER_DB_PATH = db_path

        os.makedirs(self.APP_DIR, exist_ok=True)
        self.conn = sqlite3.connect(self.USER_DB_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        self._configure()
        self.initialize()

    # -----------------------------
    # Database Configuration
    # -----------------------------
    def _configure(self):
        cursor = self.conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute("PRAGMA journal_mode = WAL;")
        cursor.execute("PRAGMA synchronous = NORMAL;")
        self.conn.commit()

    # -----------------------------
    # Schema Initialization
    # -----------------------------
    def initialize(self):
        cursor = self.conn.cursor()

        cursor.executescript("""
        CREATE TABLE IF NOT EXISTS user_profile (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            name TEXT,
            timezone TEXT,
            primary_language TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS user_preferences (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            category TEXT,
            content TEXT NOT NULL,
            embedding BLOB,
            source TEXT,
            importance INTEGER DEFAULT 1,
            confidence REAL DEFAULT 1.0,
            decay_score REAL DEFAULT 1.0,
            pinned INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_accessed TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS memory_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_id_a INTEGER,
            memory_id_b INTEGER,
            relationship TEXT,
            FOREIGN KEY(memory_id_a) REFERENCES memory(id) ON DELETE CASCADE,
            FOREIGN KEY(memory_id_b) REFERENCES memory(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            summary TEXT,
            context_tags TEXT,
            importance INTEGER DEFAULT 1,
            archived INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER,
            role TEXT,
            content TEXT,
            tokens INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id)
                REFERENCES conversations(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'pending',
            priority INTEGER DEFAULT 1,
            due_date TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS knowledge_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT,
            summary TEXT,
            source TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS ai_state (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
                             
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            source TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS document_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER,
            content TEXT NOT NULL,
            embedding BLOB NOT NULL,
            chunk_index INTEGER,
            FOREIGN KEY(document_id)
                REFERENCES documents(id)
                ON DELETE CASCADE
        );


        """)

        self.conn.commit()

    # -------------------------------------------------
    # USER PROFILE
    # -------------------------------------------------
    def set_user_profile(self, name, timezone, language):
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO user_profile
                (id, name, timezone, primary_language)
                VALUES (1, ?, ?, ?)
            """, (name, timezone, language))
            self.conn.commit()
            return {"success": True}
        except Exception as e:
            self.conn.rollback()
            return {"success": False, "error": str(e)}

    def get_user_profile(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM user_profile WHERE id=1")
        row = cursor.fetchone()
        return dict(row) if row else None

    # -------------------------------------------------
    # MEMORY
    # -------------------------------------------------
    def add_memory(self, type_, category, content,
                   source="ai", importance=1, confidence=1.0):

        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO memory
                (type, category, content, source, importance, confidence)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (type_, category, content, source,
                  importance, confidence))
            self.conn.commit()
            return {"success": True}
        except Exception as e:
            self.conn.rollback()
            return {"success": False, "error": str(e)}
        
    def add_memory_with_embedding(self, type_, category, content, embedding, source="ai", importance=1, confidence=1.0):
        try:
            cursor = self.conn.cursor()
            embedding_blob = embedding.astype(np.float32).tobytes()

            cursor.execute("""
                INSERT INTO memory
                (type, category, content, embedding, source,
                importance, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (type_, category, content, embedding_blob,
            source, importance, confidence))

            self.conn.commit()
            return {"success", True}
        except Exception as e:
            self.conn.rollback()
            return{"success": False, "error": str(e)}
        
    def search_memory_by_embedding(self, query_embedding, limit=5):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, content, embedding, importance, decay_score
            FROM memory
            WHERE embedding IS NOT NULL
        """)
        rows = cursor.fetchall()
        results = []

        for r in rows:
            stored_embedding = np.frombuffer(
                r["embedding"],
                dtype=np.float32
            )
            similarity = np.dot(query_embedding, stored_embedding)
            score = similarity * r["importance"] * r["decay_score"]

            results.append({
                "id": r["id"],
                "content": r["content"],
                "score": score
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def get_relevant_memory(self, min_importance=1, limit=20):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM memory
            WHERE importance >= ?
            ORDER BY (importance * decay_score) DESC
            LIMIT ?
        """, (min_importance, limit))

        rows = cursor.fetchall()
        return [dict(r) for r in rows]

    def access_memory(self, memory_id):
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE memory
            SET last_accessed=?, decay_score=decay_score * 1.1
            WHERE id=?
        """, (datetime.utcnow(), memory_id))
        self.conn.commit()

    def decay_memories(self):
        """
        Gradually reduce decay_score over time.
        Run periodically (e.g., on app startup).
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE memory
            SET decay_score = decay_score * 0.98
            WHERE pinned = 0
        """)
        self.conn.commit()

    # -------------------------------------------------
    # CONVERSATIONS
    # -------------------------------------------------
    def create_conversation(self, title):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO conversations (title)
            VALUES (?)
        """, (title,))
        self.conn.commit()
        return cursor.lastrowid

    def add_message(self, conversation_id, role, content, tokens=0):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO messages
            (conversation_id, role, content, tokens)
            VALUES (?, ?, ?, ?)
        """, (conversation_id, role, content, tokens))
        self.conn.commit()

    def get_conversation_messages(self, conversation_id):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM messages
            WHERE conversation_id=?
            ORDER BY created_at ASC
        """, (conversation_id,))
        return [dict(r) for r in cursor.fetchall()]

    # -------------------------------------------------
    # TASKS
    # -------------------------------------------------
    def create_task(self, title, description=None, priority=1, due_date=None):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO tasks (title, description, priority, due_date)
            VALUES (?, ?, ?, ?)
        """, (title, description, priority, due_date))
        self.conn.commit()
        return cursor.lastrowid

    def get_active_tasks(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM tasks
            WHERE status != 'completed'
            ORDER BY priority DESC, created_at ASC
        """)
        return [dict(r) for r in cursor.fetchall()]

    def update_task_status(self, task_id, status):
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE tasks
            SET status=?
            WHERE id=?
        """, (status, task_id))
        self.conn.commit()

    # -------------------------------------------------
    # AI STATE
    # -------------------------------------------------
    def set_state(self, key, value):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO ai_state
            (key, value, updated_at)
            VALUES (?, ?, ?)
        """, (key, value, datetime.utcnow()))
        self.conn.commit()

    def get_state(self, key):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT value FROM ai_state WHERE key=?
        """, (key,))
        row = cursor.fetchone()
        return row["value"] if row else None

    # -------------------------------------------------
    # Utility
    # -------------------------------------------------
    def close(self):
        self.conn.close()
    
    def create_document(self, title, source=None):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            Insert INTO documents (title, source)
            VALUES (?, ?)
            """,
            (title, source)
        )
        self.conn.commit()
        return cursor.lastrowid
    
    def add_document_chunk(self, document_id, content, embedding, chunk_index):
        cursor = self.conn.cursor()

        embedding_blob = embedding.astype(np.float32).tobytes()

        cursor.execute(
            """
            INSERT INTO document_chunks
            (document_id, content, embedding, chunk_index)
            VALUES (?, ?, ?, ?)
            """,
            (document_id, content, embedding_blob, chunk_index)
        )

        self.conn.commit()
    
    def get_all_chunks(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM document_chunks")

        rows = cursor.fetchall()

        results = []
        for r in rows:
            results.append({
                "id": r["id"],
                "document_id": r["document_id"],
                "content": r["content"],
                "embedding": np.frombuffer(r["embedding"], dtype=np.float32)
            })

        return results