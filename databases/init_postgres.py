import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()


def create_tables():
    """Crée toutes les tables PostgreSQL"""
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        database=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD")
    )

    cursor = conn.cursor()

    # Table users
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            matricule VARCHAR(50) PRIMARY KEY,
            nom VARCHAR(100) NOT NULL,
            prenom VARCHAR(100) NOT NULL,
            email VARCHAR(150) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            role VARCHAR(50) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Table user_sessions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            matricule VARCHAR(50) PRIMARY KEY,
            login_time TIMESTAMP,
            last_activity TIMESTAMP,
            logout_time TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (matricule) REFERENCES users(matricule) ON DELETE CASCADE
        )
    """)

    # Table conversations
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

    # Table message_feedback
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

    conn.commit()
    cursor.close()
    conn.close()

    print("✅ Tables PostgreSQL créées avec succès!")


if __name__ == "__main__":
    create_tables()
