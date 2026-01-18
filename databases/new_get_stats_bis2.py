import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from dotenv import load_dotenv
import os
import sys

sys.path.append(".")
from src.vectorstore import get_vector_store

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
    conn.cursor_factory = RealDictCursor
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


# ===== STATISTIQUES EXISTANTES =====

def get_all_feedbacks():
    """Récupère tous les feedbacks pour analyse"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT matricule, conversation_name, message_index, feedback_type, timestamp
            FROM message_feedback
            ORDER BY timestamp DESC
        """)
        rows = cursor.fetchall()
        cursor.close()

    return [(row['matricule'], row['conversation_name'], row['message_index'],
             row['feedback_type'], row['timestamp']) for row in rows]


def get_feedback_stats():
    """Récupère les statistiques globales des feedbacks"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT feedback_type, COUNT(*) as count
            FROM message_feedback
            GROUP BY feedback_type
        """)
        rows = cursor.fetchall()
        cursor.close()

    stats = {"positive": 0, "negative": 0}
    for row in rows:
        stats[row['feedback_type']] = row['count']
    return stats


def get_user_stats():
    """Récupère les statistiques par utilisateur"""
    with get_conn() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 
                c.matricule,
                COUNT(CASE WHEN c.role = 'user' THEN 1 END) as total_questions,
                COUNT(CASE WHEN c.role = 'assistant' THEN 1 END) as total_responses,
                COUNT(DISTINCT c.conv_name) as total_conversations,
                MIN(c.timestamp) as first_activity,
                MAX(c.timestamp) as last_activity
            FROM conversations c
            GROUP BY c.matricule
        """)
        user_rows = cursor.fetchall()

        cursor.execute("""
            SELECT 
                matricule,
                COUNT(CASE WHEN feedback_type = 'positive' THEN 1 END) as positive_feedbacks,
                COUNT(CASE WHEN feedback_type = 'negative' THEN 1 END) as negative_feedbacks
            FROM message_feedback
            GROUP BY matricule
        """)
        feedback_rows = cursor.fetchall()
        cursor.close()

    feedback_stats = {
        row['matricule']: {
            "positive": row['positive_feedbacks'],
            "negative": row['negative_feedbacks']
        } for row in feedback_rows
    }

    result = []
    for row in user_rows:
        matricule = row['matricule']
        feedbacks = feedback_stats.get(matricule, {"positive": 0, "negative": 0})
        result.append({
            "matricule": matricule,
            "total_questions": row['total_questions'],
            "total_responses": row['total_responses'],
            "total_conversations": row['total_conversations'],
            "first_activity": row['first_activity'],
            "last_activity": row['last_activity'],
            "positive_feedbacks": feedbacks["positive"],
            "negative_feedbacks": feedbacks["negative"]
        })

    return result


def get_conversation_stats():
    """Récupère les statistiques des conversations"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                conv_name, matricule, COUNT(*) as message_count,
                MIN(timestamp) as created_at, MAX(timestamp) as last_message_at
            FROM conversations
            GROUP BY conv_name, matricule
            ORDER BY last_message_at DESC
        """)
        rows = cursor.fetchall()
        cursor.close()

    return [(row['conv_name'], row['matricule'], row['message_count'],
             row['created_at'], row['last_message_at']) for row in rows]


def get_daily_activity():
    """Récupère l'activité quotidienne"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                DATE(timestamp) as date,
                COUNT(CASE WHEN role = 'user' THEN 1 END) as questions,
                COUNT(CASE WHEN role = 'assistant' THEN 1 END) as responses,
                COUNT(DISTINCT matricule) as active_users
            FROM conversations
            GROUP BY DATE(timestamp)
            ORDER BY date DESC
            LIMIT 30
        """)
        rows = cursor.fetchall()
        cursor.close()

    return [(str(row['date']), row['questions'], row['responses'], row['active_users'])
            for row in rows]


def get_connected_users():
    """Récupère la liste des utilisateurs qui ont utilisé le chat"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT c.matricule, MAX(c.timestamp) as last_activity
            FROM conversations c
            GROUP BY c.matricule
            ORDER BY last_activity DESC
        """)
        rows = cursor.fetchall()
        cursor.close()

    return [(row['matricule'], row['last_activity']) for row in rows]


# ===== NOUVELLES STATISTIQUES =====

def get_total_users():
    """Nombre total d'utilisateurs inscrits"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM users")
        result = cursor.fetchone()
        cursor.close()
    return result['count']


def get_total_documents():
    """Nombre total de documents chargés"""
    try:
        vector_store = get_vector_store()
        results = vector_store.get(include=["metadatas"])
        metadatas = results["metadatas"]

        unique_doc_ids = set()
        for meta in metadatas:
            doc_id = meta.get("doc_id")
            if doc_id:
                unique_doc_ids.add(doc_id)

        return len(unique_doc_ids)
    except:
        return 0


def get_documents_by_type():
    """Statistiques des documents par type"""
    try:
        vector_store = get_vector_store()
        results = vector_store.get(include=["metadatas"])
        metadatas = results["metadatas"]

        doc_types = {}
        seen_docs = set()

        for meta in metadatas:
            doc_id = meta.get("doc_id")
            filename = meta.get("filename", "")

            if doc_id and doc_id not in seen_docs:
                seen_docs.add(doc_id)

                if filename.endswith('.pdf'):
                    doc_type = 'PDF'
                elif filename.endswith(('.xlsx', '.xls')):
                    doc_type = 'Excel'
                elif filename.endswith('.csv'):
                    doc_type = 'CSV'
                else:
                    doc_type = 'Autre'

                doc_types[doc_type] = doc_types.get(doc_type, 0) + 1

        return doc_types
    except:
        return {}


def get_users_connected_now(exclude_admin=False):
    """
    Nombre d'utilisateurs actuellement connectés (is_active = 1)
    """
    _cleanup_ghost_sessions()

    with get_conn() as conn:
        cursor = conn.cursor()
        if exclude_admin:
            cursor.execute("""
                SELECT COUNT(DISTINCT s.matricule) as count
                FROM user_sessions s
                JOIN users u ON s.matricule = u.matricule
                WHERE s.is_active = 1 AND u.role != 'admin'
            """)
        else:
            cursor.execute("""
                SELECT COUNT(DISTINCT matricule) as count
                FROM user_sessions
                WHERE is_active = 1
            """)
        result = cursor.fetchone()
        cursor.close()

    return result['count']


def _cleanup_ghost_sessions():
    """Nettoie les sessions 'fantômes'"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE user_sessions 
            SET is_active = 0, logout_time = CURRENT_TIMESTAMP
            WHERE is_active = 1 
            AND login_time < CURRENT_TIMESTAMP - INTERVAL '12 hours'
        """)
        cursor.close()


def get_users_connected_today():
    """Utilisateurs connectés aujourd'hui"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.matricule, u.nom, u.prenom, u.role, 
                   s.login_time, s.is_active
            FROM user_sessions s
            JOIN users u ON s.matricule = u.matricule
            WHERE DATE(s.login_time) = CURRENT_DATE
            ORDER BY s.login_time DESC
        """)
        rows = cursor.fetchall()
        cursor.close()

    return [(row['matricule'], row['nom'], row['prenom'], row['role'],
             row['login_time'], row['is_active']) for row in rows]


def get_active_users_now(exclude_admin=False):
    """Liste des utilisateurs actuellement connectés"""
    _cleanup_ghost_sessions()

    with get_conn() as conn:
        cursor = conn.cursor()
        if exclude_admin:
            cursor.execute("""
                SELECT u.matricule, u.nom, u.prenom, u.role, s.login_time
                FROM user_sessions s
                JOIN users u ON s.matricule = u.matricule
                WHERE s.is_active = 1 AND u.role != 'admin'
                ORDER BY s.login_time DESC
            """)
        else:
            cursor.execute("""
                SELECT u.matricule, u.nom, u.prenom, u.role, s.login_time
                FROM user_sessions s
                JOIN users u ON s.matricule = u.matricule
                WHERE s.is_active = 1
                ORDER BY s.login_time DESC
            """)
        rows = cursor.fetchall()
        cursor.close()

    return [(row['matricule'], row['nom'], row['prenom'], row['role'], row['login_time'])
            for row in rows]


def get_total_conversations():
    """Nombre total de conversations"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(DISTINCT conv_name || '_' || matricule) as count
            FROM conversations
        """)
        result = cursor.fetchone()
        cursor.close()
    return result['count']


def get_conversations_by_day():
    """Évolution des conversations par jour (30 derniers jours)"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                DATE(timestamp) as date,
                COUNT(DISTINCT conv_name || '_' || matricule) as conv_count,
                EXTRACT(DOW FROM timestamp) as day_num
            FROM conversations
            WHERE timestamp >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY DATE(timestamp), EXTRACT(DOW FROM timestamp)
            ORDER BY date ASC
        """)
        rows = cursor.fetchall()
        cursor.close()

    # Mapping des jours en français
    jour_mapping = {
        0: 'Dimanche',
        1: 'Lundi',
        2: 'Mardi',
        3: 'Mercredi',
        4: 'Jeudi',
        5: 'Vendredi',
        6: 'Samedi'
    }

    return [(str(row['date']), row['conv_count'], jour_mapping[int(row['day_num'])]) for row in rows]


def get_conversations_by_weekday():
    """Moyenne des conversations par jour de la semaine"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                EXTRACT(DOW FROM timestamp) as day_num,
                COUNT(DISTINCT DATE(timestamp) || '_' || conv_name || '_' || matricule) as total_convs,
                COUNT(DISTINCT DATE(timestamp)) as days_count,
                CAST(COUNT(DISTINCT DATE(timestamp) || '_' || conv_name || '_' || matricule) AS FLOAT) / 
                NULLIF(COUNT(DISTINCT DATE(timestamp)), 0) as avg_convs
            FROM conversations
            GROUP BY EXTRACT(DOW FROM timestamp)
            ORDER BY day_num
        """)
        rows = cursor.fetchall()
        cursor.close()

    # Mapping PostgreSQL DOW (0=Dimanche, 1=Lundi, ...) vers jours français
    jour_mapping = {
        0: 'Dimanche',
        1: 'Lundi',
        2: 'Mardi',
        3: 'Mercredi',
        4: 'Jeudi',
        5: 'Vendredi',
        6: 'Samedi'
    }

    return [(jour_mapping[int(row['day_num'])], row['avg_convs']) for row in rows]


def get_user_types():
    """Répartition des utilisateurs par type/rôle"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT role, COUNT(*) as count
            FROM users
            GROUP BY role
        """)
        rows = cursor.fetchall()
        cursor.close()

    return {row['role']: row['count'] for row in rows}


# ===== STATISTIQUES TEMPS DE RÉPONSE =====

def get_average_response_time():
    """Temps de réponse moyen global (en secondes)"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT AVG(response_time) as avg_time
            FROM conversations
            WHERE role = 'assistant' AND response_time IS NOT NULL
        """)
        result = cursor.fetchone()
        cursor.close()

    return result['avg_time'] if result['avg_time'] else 0


def get_response_time_by_day():
    """Temps de réponse moyen par jour (30 derniers jours)"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                DATE(timestamp) as date,
                AVG(response_time) as avg_time,
                COUNT(*) as response_count
            FROM conversations
            WHERE role = 'assistant' 
            AND response_time IS NOT NULL
            AND timestamp >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY DATE(timestamp)
            ORDER BY date ASC
        """)
        rows = cursor.fetchall()
        cursor.close()

    return [(str(row['date']), row['avg_time'], row['response_count']) for row in rows]


def get_response_time_distribution():
    """Distribution des temps de réponse par tranche"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN response_time < 3 THEN '< 3s'
                    WHEN response_time < 5 THEN '3-5s'
                    WHEN response_time < 10 THEN '5-10s'
                    WHEN response_time < 15 THEN '10-15s'
                    ELSE '> 15s'
                END as time_range,
                COUNT(*) as count
            FROM conversations
            WHERE role = 'assistant' AND response_time IS NOT NULL
            GROUP BY 
                CASE 
                    WHEN response_time < 3 THEN '< 3s'
                    WHEN response_time < 5 THEN '3-5s'
                    WHEN response_time < 10 THEN '5-10s'
                    WHEN response_time < 15 THEN '10-15s'
                    ELSE '> 15s'
                END
            ORDER BY 
                MIN(CASE 
                    WHEN response_time < 3 THEN 1
                    WHEN response_time < 5 THEN 2
                    WHEN response_time < 10 THEN 3
                    WHEN response_time < 15 THEN 4
                    ELSE 5
                END)
        """)
        rows = cursor.fetchall()
        cursor.close()

    return {row['time_range']: row['count'] for row in rows}


def get_response_time_by_user():
    """Temps de réponse moyen par utilisateur"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                c.matricule,
                AVG(c.response_time) as avg_time,
                COUNT(*) as response_count,
                MIN(c.response_time) as min_time,
                MAX(c.response_time) as max_time
            FROM conversations c
            WHERE c.role = 'assistant' AND c.response_time IS NOT NULL
            GROUP BY c.matricule
            ORDER BY avg_time DESC
        """)
        rows = cursor.fetchall()
        cursor.close()

    return [(row['matricule'], row['avg_time'], row['response_count'],
             row['min_time'], row['max_time']) for row in rows]
