import sqlite3
import streamlit as st
import hashlib
from datetime import datetime

DB_PATH = "users.db"

def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def create_users_table():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            matricule TEXT PRIMARY KEY,
            nom TEXT,
            prenom TEXT,
            email TEXT,
            password TEXT,
            role TEXT
        )
    """)

    # Table pour tracker les connexions (UNE ligne par utilisateur)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            matricule TEXT PRIMARY KEY,
            login_time DATETIME,
            last_activity DATETIME,
            logout_time DATETIME,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (matricule) REFERENCES users(matricule)
        )
    """)

    conn.commit()
    conn.close()

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed

def register_user(matricule, nom, prenom, email, password, role):
    conn = get_connection()
    conn.execute(
        "INSERT INTO users (matricule, nom, prenom, email, password, role) VALUES (?, ?, ?, ?, ?, ?)",
        (matricule, nom, prenom, email, hash_password(password), role)
    )
    conn.commit()
    conn.close()

def update_session_activity(matricule):
    """Met à jour l'activité de la session (appelé automatiquement)"""
    conn = get_connection()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Vérifier si une session existe
    cursor = conn.execute(
        "SELECT matricule FROM user_sessions WHERE matricule = ? AND is_active = 1",
        (matricule,)
    )

    if cursor.fetchone():
        # Mettre à jour l'activité
        conn.execute(
            "UPDATE user_sessions SET last_activity = ? WHERE matricule = ?",
            (now, matricule)
        )

    conn.commit()
    conn.close()

def login_user(matricule, password):
    conn = get_connection()
    cursor = conn.execute("SELECT matricule, nom, prenom, email, password, role FROM users WHERE matricule = ?",
                          (matricule,))
    row = cursor.fetchone()

    if row and verify_password(password, row[4]):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Vérifier si une session active existe déjà
        existing = conn.execute(
            "SELECT matricule FROM user_sessions WHERE matricule = ?",
            (row[0],)
        ).fetchone()

        if existing:
            # Mettre à jour la session existante
            conn.execute("""
                UPDATE user_sessions 
                SET login_time = ?, last_activity = ?, is_active = 1, logout_time = NULL
                WHERE matricule = ?
            """, (now, now, row[0]))
        else:
            # Créer une nouvelle session
            conn.execute("""
                INSERT INTO user_sessions (matricule, login_time, last_activity, is_active)
                VALUES (?, ?, ?, 1)
            """, (row[0], now, now))

        conn.commit()

        st.session_state.logged_in = True
        st.session_state.matricule = row[0]
        st.session_state.nom = row[1]
        st.session_state.prenom = row[2]
        st.session_state.email = row[3]
        st.session_state.role = row[5]

        conn.close()
        return True

    conn.close()
    return False


def logout_user():
    # Mettre à jour la session avec l'heure de déconnexion
    if "matricule" in st.session_state:
        conn = get_connection()
        conn.execute("""
            UPDATE user_sessions 
            SET logout_time = ?, is_active = 0 
            WHERE matricule = ? AND is_active = 1
        """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), st.session_state.matricule))
        conn.commit()
        conn.close()

    for key in ["logged_in", "matricule", "nom", "prenom", "email", "role"]:
        st.session_state.pop(key, None)
