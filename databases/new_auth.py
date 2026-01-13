import streamlit as st
import hashlib
from datetime import datetime
from streamlit_cookies_manager import EncryptedCookieManager
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os
from contextlib import contextmanager

# Charger les variables d'environnement
load_dotenv()

# Configuration PostgreSQL
DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": os.getenv("POSTGRES_PORT", "5432"),
    "database": os.getenv("POSTGRES_DB"),
    "user": os.getenv("POSTGRES_USER"),
    "password": os.getenv("POSTGRES_PASSWORD")
}

# Initialiser le gestionnaire de cookies
cookies = EncryptedCookieManager(
    prefix="chatbot_",
    password=os.getenv("COOKIE_SECRET", "VotreCleSecreteTresLongueEtComplexe123!")
)

if not cookies.ready():
    st.stop()


@contextmanager
def get_connection():
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


def create_users_table():
    """Crée les tables si elles n'existent pas"""
    with get_connection() as conn:
        cursor = conn.cursor()

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

        cursor.close()


def hash_password(password: str) -> str:
    """Hash un mot de passe avec SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    """Vérifie un mot de passe hashé"""
    return hash_password(password) == hashed


def register_user(matricule, nom, prenom, email, password, role):
    """Enregistre un nouvel utilisateur"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO users (matricule, nom, prenom, email, password, role) 
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (matricule, nom, prenom, email, hash_password(password), role)
        )
        cursor.close()


def save_session_to_cookies(matricule, nom, prenom, email, role):
    """Sauvegarde la session dans les cookies"""
    cookies['matricule'] = matricule
    cookies['nom'] = nom
    cookies['prenom'] = prenom
    cookies['email'] = email
    cookies['role'] = role
    cookies['logged_in'] = 'true'
    cookies.save()


def restore_session_from_cookies():
    """Restaure la session depuis les cookies"""
    if cookies.get('logged_in') == 'true':
        st.session_state.logged_in = True
        st.session_state.matricule = cookies.get('matricule')
        st.session_state.nom = cookies.get('nom')
        st.session_state.prenom = cookies.get('prenom')
        st.session_state.email = cookies.get('email')
        st.session_state.role = cookies.get('role')
        return True
    return False


def clear_cookies():
    """Efface tous les cookies de session"""
    cookies['logged_in'] = 'false'
    cookies['matricule'] = ''
    cookies['nom'] = ''
    cookies['prenom'] = ''
    cookies['email'] = ''
    cookies['role'] = ''
    cookies.save()


def login_user(matricule, password):
    """Authentifie un utilisateur"""
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """SELECT matricule, nom, prenom, email, password, role 
               FROM users WHERE matricule = %s""",
            (matricule,)
        )
        row = cursor.fetchone()

        if row and verify_password(password, row['password']):
            now = datetime.now()

            # Vérifier si une session existe déjà
            cursor.execute(
                "SELECT matricule FROM user_sessions WHERE matricule = %s",
                (row['matricule'],)
            )
            existing = cursor.fetchone()

            if existing:
                cursor.execute("""
                    UPDATE user_sessions 
                    SET login_time = %s, last_activity = %s, is_active = 1, logout_time = NULL
                    WHERE matricule = %s
                """, (now, now, row['matricule']))
            else:
                cursor.execute("""
                    INSERT INTO user_sessions (matricule, login_time, last_activity, is_active)
                    VALUES (%s, %s, %s, 1)
                """, (row['matricule'], now, now))

            # Sauvegarder dans session_state
            st.session_state.logged_in = True
            st.session_state.matricule = row['matricule']
            st.session_state.nom = row['nom']
            st.session_state.prenom = row['prenom']
            st.session_state.email = row['email']
            st.session_state.role = row['role']

            # Sauvegarder dans les cookies
            save_session_to_cookies(
                row['matricule'],
                row['nom'],
                row['prenom'],
                row['email'],
                row['role']
            )

            cursor.close()
            return True

        cursor.close()
        return False


def logout_user():
    """Déconnecte un utilisateur"""
    if "matricule" in st.session_state:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE user_sessions 
                SET logout_time = %s, is_active = 0 
                WHERE matricule = %s AND is_active = 1
            """, (datetime.now(), st.session_state.matricule))
            cursor.close()

    # Effacer session_state
    for key in ["logged_in", "matricule", "nom", "prenom", "email", "role"]:
        st.session_state.pop(key, None)

    # Effacer les cookies
    clear_cookies()


def check_and_restore_session():
    """
    À appeler au début de chaque page pour restaurer la session
    si elle existe dans les cookies mais pas dans session_state
    """
    if "logged_in" not in st.session_state or not st.session_state.logged_in:
        return restore_session_from_cookies()
    return True
