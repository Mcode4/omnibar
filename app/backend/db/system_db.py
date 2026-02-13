import os
import sqlite3
import shutil
from datetime import datetime

APP_DIR = os.path.expanduser("~/.local/share/omnimanager")
SYSTEM_DB_PATH = os.path.join(APP_DIR, "system.db")
BACKUP_DB_PATH = os.path.join(APP_DIR, "system_backup.db")


class SystemDatabase:
    def __init__(self):
        os.makedirs(APP_DIR, exist_ok=True)

        self._ensure_integrity()

        self.conn = sqlite3.connect(
            SYSTEM_DB_PATH,
            check_same_thread=False
        )
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")

        self.initialize()
        self._create_backup()

    # =========================
    # INTEGRITY + ROLLBACK
    # =========================

    def _ensure_integrity(self):
        if not os.path.exists(SYSTEM_DB_PATH):
            return

        try:
            conn = sqlite3.connect(SYSTEM_DB_PATH)
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            result = cursor.fetchone()[0]
            conn.close()

            if result != "ok":
                raise Exception("Integrity check failed")

        except Exception:
            print("⚠️ Database corrupted. Attempting rollback...")

            if os.path.exists(BACKUP_DB_PATH):
                shutil.copy(BACKUP_DB_PATH, SYSTEM_DB_PATH)
                print("✅ Restored from backup.")
            else:
                corrupted_name = SYSTEM_DB_PATH + ".corrupt_" + datetime.now().strftime("%Y%m%d%H%M%S")
                shutil.move(SYSTEM_DB_PATH, corrupted_name)
                print("⚠️ No backup found. Created new DB.")

    def _create_backup(self):
        if os.path.exists(SYSTEM_DB_PATH):
            shutil.copy(SYSTEM_DB_PATH, BACKUP_DB_PATH)

    # =========================
    # INITIALIZATION
    # =========================

    def initialize(self):
        cursor = self.conn.cursor()

        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                system_prompt TEXT,
                temperature REAL DEFAULT 0.7,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                pinned INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME
            );

            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT,
                message TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        """)

        self.conn.commit()

    # =========================
    # CHAT METHODS
    # =========================

    def get_chats(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM chats ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

    def create_chat(self, title):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO chats (title) VALUES (?)",
            (title,)
        )
        self.conn.commit()
        return cursor.lastrowid

    def delete_chat(self, chat_id):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM chats WHERE id=?", (chat_id,))
        self.conn.commit()

    # =========================
    # MESSAGE METHODS
    # =========================

    def get_messages_by_chat(self, chat_id):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM messages WHERE chat_id=? ORDER BY created_at ASC",
            (chat_id,)
        )
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

    def create_message(self, chat_id, role, content):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO messages (chat_id, role, content) VALUES (?, ?, ?)",
            (chat_id, role, content)
        )
        self.conn.commit()

    # =========================
    # NOTES METHODS
    # =========================

    def get_all_notes(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM notes ORDER BY updated_at DESC")
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

    def create_note(self, title, content=""):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO notes (title, content) VALUES (?, ?)",
            (title, content)
        )
        self.conn.commit()

    def update_note(self, note_id, title, content):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE notes
            SET title=?, content=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (title, content, note_id)
        )
        self.conn.commit()

    def delete_note(self, note_id):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM notes WHERE id=?", (note_id,))
        self.conn.commit()

    # =========================
    # LOGGING
    # =========================

    def append_log(self, level, message):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO logs (level, message) VALUES (?, ?)",
            (level, message)
        )
        self.conn.commit()

    def get_logs(self, level=None):
        cursor = self.conn.cursor()
        if level:
            cursor.execute(
                "SELECT * FROM logs WHERE level=? ORDER BY created_at DESC",
                (level,)
            )
        else:
            cursor.execute(
                "SELECT * FROM logs ORDER BY created_at DESC"
            )

        rows = cursor.fetchall()
        return [dict(r) for r in rows]

    # =========================
    # SETTINGS
    # =========================

    def get_setting(self, key):
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = cursor.fetchone()
        return row["value"] if row else None

    def set_setting(self, key, value):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """,
            (key, value)
        )
        self.conn.commit()

        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                """
            )
            self.conn.commit()
        
        except Exception as e:
            errorRes = {
                "message": f"Error occured while changing settings",
                "error": e,
                "level": ""
            }
            print(errorRes)
            return errorRes
        return {
            "message": f"Successfully changed settings",
            "level": ""
        }