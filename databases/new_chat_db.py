import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from dotenv import load_dotenv
import os
from datetime import datetime

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": os.getenv("POSTGRES_PORT", "5432"),
    "database": os.getenv("POSTGRES_DB"),
    "user": os.getenv("POSTGRES_USER"),
    "password": os.getenv("POSTGRES_PASSWORD")
}


@contextmanager
def get_conn():
    """Context manager pour les connexions PostgreSQL"""
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def init_chat_table():
    """Initialise les tables de chat"""
    with get_conn() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id SERIAL PRIMARY KEY,
                matricule VARCHAR(50) NOT NULL,
                conv_name VARCHAR(255) NOT NULL,
                role VARCHAR(20) NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                response_time REAL,
                FOREIGN KEY (matricule) REFERENCES users(matricule) ON DELETE CASCADE
            )
        """)

        # Index pour améliorer les performances
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversations_matricule 
            ON conversations(matricule)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversations_conv_name 
            ON conversations(conv_name)
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS message_feedback (
                id SERIAL PRIMARY KEY,
                matricule VARCHAR(50) NOT NULL,
                conversation_name VARCHAR(255) NOT NULL,
                message_index INTEGER NOT NULL,
                feedback_type VARCHAR(20) NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (matricule) REFERENCES users(matricule) ON DELETE CASCADE,
                UNIQUE(matricule, conversation_name, message_index)
            )
        """)

        cursor.close()


def save_message(matricule, conv_name, role, content, response_time=None):
    """Sauvegarde un message dans la base"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO conversations 
               (matricule, conv_name, role, content, response_time) 
               VALUES (%s, %s, %s, %s, %s)""",
            (matricule, conv_name, role, content, response_time)
        )
        cursor.close()


def load_conversations(matricule):
    """Charge toutes les conversations d'un utilisateur"""
    with get_conn() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """SELECT conv_name, role, content 
               FROM conversations 
               WHERE matricule = %s 
               ORDER BY id ASC""",
            (matricule,)
        )
        rows = cursor.fetchall()
        cursor.close()

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
    """Supprime une conversation entière"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM conversations WHERE matricule = %s AND conv_name = %s",
            (matricule, conversation_name)
        )
        cursor.close()


def rename_conversation(matricule, old_name, new_name):
    """Renomme une conversation"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE conversations 
            SET conv_name = %s 
            WHERE matricule = %s AND conv_name = %s
        """, (new_name, matricule, old_name))
        cursor.close()


def save_feedback(matricule, conversation_name, message_index, feedback_type):
    """Sauvegarde ou met à jour le feedback d'un message"""
    with get_conn() as conn:
        cursor = conn.cursor()

        # Utiliser INSERT ... ON CONFLICT pour PostgreSQL
        cursor.execute("""
            INSERT INTO message_feedback 
            (matricule, conversation_name, message_index, feedback_type, timestamp)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (matricule, conversation_name, message_index) 
            DO UPDATE SET 
                feedback_type = EXCLUDED.feedback_type,
                timestamp = EXCLUDED.timestamp
        """, (matricule, conversation_name, message_index, feedback_type, datetime.now()))

        cursor.close()


def get_feedback(matricule, conversation_name, message_index):
    """Récupère le feedback d'un message"""
    with get_conn() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT feedback_type 
            FROM message_feedback 
            WHERE matricule = %s AND conversation_name = %s AND message_index = %s
        """, (matricule, conversation_name, message_index))

        result = cursor.fetchone()
        cursor.close()

        return result['feedback_type'] if result else None
