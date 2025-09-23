import sqlite3
import streamlit as st
import hashlib
import os

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
    conn.commit()
    conn.close()

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed

def register_user(matricule, nom, prenom, email, password, role):
    # role="user"
    conn = get_connection()
    conn.execute(
        "INSERT INTO users (matricule, nom, prenom, email, password, role) VALUES (?, ?, ?, ?, ?, ?)",
        (matricule, nom, prenom, email, hash_password(password), role)
    )
    conn.commit()
    conn.close()

def login_user(matricule, password):
    conn = get_connection()
    cursor = conn.execute("SELECT matricule, nom, prenom, email, password, role FROM users WHERE matricule = ?", (matricule,))
    row = cursor.fetchone()
    conn.close()

    if row and verify_password(password, row[4]):
        st.session_state.logged_in = True
        st.session_state.matricule = row[0]
        st.session_state.nom = row[1]
        st.session_state.prenom = row[2]
        st.session_state.email = row[3]
        st.session_state.role = row[5]
        return True
    return False

def logout_user():
    for key in ["logged_in", "matricule", "nom", "prenom", "email", "role"]:
        st.session_state.pop(key, None)
