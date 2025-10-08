import sqlite3
from contextlib import contextmanager

DB_PATH = "users.db"

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.commit()
    conn.close()

def init_chat_table():
    with get_conn() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            matricule TEXT,
            conv_name TEXT,
            role TEXT,
            content TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

def save_message(matricule, conv_name, role, content):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO conversations (matricule, conv_name, role, content) VALUES (?, ?, ?, ?)",
            (matricule, conv_name, role, content)
        )

def load_conversations(matricule):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT conv_name, role, content FROM conversations WHERE matricule = ? ORDER BY id ASC",
            (matricule,)
        ).fetchall()

    conversations = {}
    for row in rows:
        if row["conv_name"] not in conversations:
            conversations[row["conv_name"]] = []
        conversations[row["conv_name"]].append({
            "role": row["role"],
            "content": row["content"]
        })
    return conversations

def delete_conversation(matricule, conversation_name):
    """Supprime une conversation entière (tous les messages) pour un utilisateur donné."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM conversations WHERE matricule = ? AND conv_name = ?",
        (matricule, conversation_name),
    )
    conn.commit()
    conn.close()

def rename_conversation(matricule, old_name, new_name):
    """Renomme une conversation dans la base de données"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE conversations 
        SET conv_name = ? 
        WHERE matricule = ? AND conv_name = ?
    """, (new_name, matricule, old_name))
    conn.commit()
    conn.close()
