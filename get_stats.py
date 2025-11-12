import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
import sys

sys.path.append(".")
from src.vectorstore import get_vector_store

DB_PATH = "users.db"


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.commit()
    conn.close()


# ===== STATISTIQUES EXISTANTES =====

def get_all_feedbacks():
    """Récupère tous les feedbacks pour analyse"""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT matricule, conversation_name, message_index, feedback_type, timestamp
            FROM message_feedback
            ORDER BY timestamp DESC
        """).fetchall()
    return [(row['matricule'], row['conversation_name'], row['message_index'],
             row['feedback_type'], row['timestamp']) for row in rows]


def get_feedback_stats():
    """Récupère les statistiques globales des feedbacks"""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT feedback_type, COUNT(*) as count
            FROM message_feedback
            GROUP BY feedback_type
        """).fetchall()

    stats = {"positive": 0, "negative": 0}
    for row in rows:
        stats[row['feedback_type']] = row['count']
    return stats


def get_user_stats():
    """Récupère les statistiques par utilisateur"""
    with get_conn() as conn:
        user_rows = conn.execute("""
            SELECT 
                c.matricule,
                COUNT(CASE WHEN c.role = 'user' THEN 1 END) as total_questions,
                COUNT(CASE WHEN c.role = 'assistant' THEN 1 END) as total_responses,
                COUNT(DISTINCT c.conv_name) as total_conversations,
                MIN(c.timestamp) as first_activity,
                MAX(c.timestamp) as last_activity
            FROM conversations c
            GROUP BY c.matricule
        """).fetchall()

        feedback_rows = conn.execute("""
            SELECT 
                matricule,
                COUNT(CASE WHEN feedback_type = 'positive' THEN 1 END) as positive_feedbacks,
                COUNT(CASE WHEN feedback_type = 'negative' THEN 1 END) as negative_feedbacks
            FROM message_feedback
            GROUP BY matricule
        """).fetchall()

    feedback_stats = {row['matricule']: {"positive": row['positive_feedbacks'],
                                         "negative": row['negative_feedbacks']}
                      for row in feedback_rows}

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
        rows = conn.execute("""
            SELECT 
                conv_name, matricule, COUNT(*) as message_count,
                MIN(timestamp) as created_at, MAX(timestamp) as last_message_at
            FROM conversations
            GROUP BY conv_name, matricule
            ORDER BY last_message_at DESC
        """).fetchall()

    return [(row['conv_name'], row['matricule'], row['message_count'],
             row['created_at'], row['last_message_at']) for row in rows]


def get_daily_activity():
    """Récupère l'activité quotidienne"""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT 
                DATE(timestamp) as date,
                COUNT(CASE WHEN role = 'user' THEN 1 END) as questions,
                COUNT(CASE WHEN role = 'assistant' THEN 1 END) as responses,
                COUNT(DISTINCT matricule) as active_users
            FROM conversations
            GROUP BY DATE(timestamp)
            ORDER BY date DESC
            LIMIT 30
        """).fetchall()

    return [(row['date'], row['questions'], row['responses'], row['active_users'])
            for row in rows]


def get_connected_users():
    """Récupère la liste des utilisateurs qui ont utilisé le chat"""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT DISTINCT c.matricule, MAX(c.timestamp) as last_activity
            FROM conversations c
            GROUP BY c.matricule
            ORDER BY last_activity DESC
        """).fetchall()

    return [(row['matricule'], row['last_activity']) for row in rows]


# ===== NOUVELLES STATISTIQUES =====

def get_total_users():
    """Nombre total d'utilisateurs inscrits"""
    with get_conn() as conn:
        result = conn.execute("SELECT COUNT(*) as count FROM users").fetchone()
    return result['count']


def get_total_documents():
    """Nombre total de documents chargés"""
    try:
        vector_store = get_vector_store()
        results = vector_store.get(include=["metadatas"])
        metadatas = results["metadatas"]

        # Compter les documents uniques par doc_id
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

        # Compter les types de documents uniques
        doc_types = {}
        seen_docs = set()

        for meta in metadatas:
            doc_id = meta.get("doc_id")
            filename = meta.get("filename", "")

            # Éviter de compter plusieurs fois le même document
            if doc_id and doc_id not in seen_docs:
                seen_docs.add(doc_id)

                # Déterminer le type
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
    exclude_admin: Si True, n'inclut pas les admins dans le comptage
    """
    # D'abord, nettoyer les sessions fantômes (connectées depuis plus de 12h)
    _cleanup_ghost_sessions()

    with get_conn() as conn:
        if exclude_admin:
            result = conn.execute("""
                SELECT COUNT(DISTINCT s.matricule) as count
                FROM user_sessions s
                JOIN users u ON s.matricule = u.matricule
                WHERE s.is_active = 1 AND u.role != 'admin'
            """).fetchone()
        else:
            result = conn.execute("""
                SELECT COUNT(DISTINCT matricule) as count
                FROM user_sessions
                WHERE is_active = 1
            """).fetchone()
    return result['count']


def _cleanup_ghost_sessions():
    """
    Nettoie les sessions 'fantômes' - connectées depuis trop longtemps sans déconnexion
    Une session est considérée fantôme si connectée depuis plus de 12 heures
    """
    with get_conn() as conn:
        conn.execute("""
            UPDATE user_sessions 
            SET is_active = 0, logout_time = datetime('now')
            WHERE is_active = 1 
            AND login_time < datetime('now', '-12 hours')
        """)


def get_users_connected_today():
    """Utilisateurs connectés aujourd'hui (unique par matricule)"""
    today = datetime.now().strftime("%Y-%m-%d")
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT u.matricule, u.nom, u.prenom, u.role, 
                   s.login_time, s.is_active
            FROM user_sessions s
            JOIN users u ON s.matricule = u.matricule
            WHERE DATE(s.login_time) = ?
            ORDER BY s.login_time DESC
        """, (today,)).fetchall()

    return [(row['matricule'], row['nom'], row['prenom'], row['role'],
             row['login_time'], row['is_active']) for row in rows]


def get_active_users_now(exclude_admin=False):
    """
    Liste des utilisateurs actuellement connectés (is_active = 1)
    exclude_admin: Si True, n'inclut pas les admins
    """
    # Nettoyer les sessions fantômes avant d'afficher
    _cleanup_ghost_sessions()

    with get_conn() as conn:
        if exclude_admin:
            rows = conn.execute("""
                SELECT u.matricule, u.nom, u.prenom, u.role, s.login_time
                FROM user_sessions s
                JOIN users u ON s.matricule = u.matricule
                WHERE s.is_active = 1 AND u.role != 'admin'
                ORDER BY s.login_time DESC
            """).fetchall()
        else:
            rows = conn.execute("""
                SELECT u.matricule, u.nom, u.prenom, u.role, s.login_time
                FROM user_sessions s
                JOIN users u ON s.matricule = u.matricule
                WHERE s.is_active = 1
                ORDER BY s.login_time DESC
            """).fetchall()

    return [(row['matricule'], row['nom'], row['prenom'], row['role'], row['login_time'])
            for row in rows]


def get_total_conversations():
    """Nombre total de conversations"""
    with get_conn() as conn:
        result = conn.execute("""
            SELECT COUNT(DISTINCT conv_name || '_' || matricule) as count
            FROM conversations
        """).fetchone()
    return result['count']


def get_conversations_by_day():
    """Évolution moyenne des conversations par jour (30 derniers jours)"""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT 
                DATE(timestamp) as date,
                COUNT(DISTINCT conv_name || '_' || matricule) as conv_count,
                CASE 
                    WHEN strftime('%w', DATE(timestamp)) = '0' THEN 'Dimanche'
                    WHEN strftime('%w', DATE(timestamp)) = '1' THEN 'Lundi'
                    WHEN strftime('%w', DATE(timestamp)) = '2' THEN 'Mardi'
                    WHEN strftime('%w', DATE(timestamp)) = '3' THEN 'Mercredi'
                    WHEN strftime('%w', DATE(timestamp)) = '4' THEN 'Jeudi'
                    WHEN strftime('%w', DATE(timestamp)) = '5' THEN 'Vendredi'
                    WHEN strftime('%w', DATE(timestamp)) = '6' THEN 'Samedi'
                END as day_name
            FROM conversations
            WHERE timestamp >= date('now', '-30 days')
            GROUP BY DATE(timestamp)
            ORDER BY date ASC
        """).fetchall()

    return [(row['date'], row['conv_count'], row['day_name']) for row in rows]


def get_conversations_by_weekday():
    """Moyenne des conversations par jour de la semaine"""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT 
                CASE 
                    WHEN strftime('%w', DATE(timestamp)) = '0' THEN 'Dimanche'
                    WHEN strftime('%w', DATE(timestamp)) = '1' THEN 'Lundi'
                    WHEN strftime('%w', DATE(timestamp)) = '2' THEN 'Mardi'
                    WHEN strftime('%w', DATE(timestamp)) = '3' THEN 'Mercredi'
                    WHEN strftime('%w', DATE(timestamp)) = '4' THEN 'Jeudi'
                    WHEN strftime('%w', DATE(timestamp)) = '5' THEN 'Vendredi'
                    WHEN strftime('%w', DATE(timestamp)) = '6' THEN 'Samedi'
                END as day_name,
                strftime('%w', DATE(timestamp)) as day_num,
                COUNT(DISTINCT DATE(timestamp) || '_' || conv_name || '_' || matricule) as total_convs,
                COUNT(DISTINCT DATE(timestamp)) as days_count,
                CAST(COUNT(DISTINCT DATE(timestamp) || '_' || conv_name || '_' || matricule) AS FLOAT) / 
                COUNT(DISTINCT DATE(timestamp)) as avg_convs
            FROM conversations
            GROUP BY strftime('%w', DATE(timestamp))
            ORDER BY day_num
        """).fetchall()

    return [(row['day_name'], row['avg_convs']) for row in rows]


def get_user_types():
    """Répartition des utilisateurs par type/rôle"""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT role, COUNT(*) as count
            FROM users
            GROUP BY role
        """).fetchall()

    return {row['role']: row['count'] for row in rows}


# ===== STATISTIQUES TEMPS DE RÉPONSE =====

def get_average_response_time():
    """Temps de réponse moyen global (en secondes)"""
    with get_conn() as conn:
        result = conn.execute("""
            SELECT AVG(response_time) as avg_time
            FROM conversations
            WHERE role = 'assistant' AND response_time IS NOT NULL
        """).fetchone()

    return result['avg_time'] if result['avg_time'] else 0

  #
  # MIN(response_time) as min_time,
  #               MAX(response_time) as max_time,
  #               COUNT(*) as response_count

def get_response_time_by_day():
    """Temps de réponse moyen par jour (30 derniers jours)"""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT 
                DATE(timestamp) as date,
                response_time as rsp_time
            FROM conversations
            WHERE role = 'assistant' 
            AND response_time IS NOT NULL
            AND timestamp >= date('now')
        """).fetchall()

    return [(row['date'], row['rsp_time']) for row in rows]


def get_response_time_distribution():
    """Distribution des temps de réponse par tranche"""
    with get_conn() as conn:
        rows = conn.execute("""
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
            GROUP BY time_range
            ORDER BY 
                CASE time_range
                    WHEN '< 3s' THEN 1
                    WHEN '3-5s' THEN 2
                    WHEN '5-10s' THEN 3
                    WHEN '10-15s' THEN 4
                    ELSE 5
                END
        """).fetchall()

    return {row['time_range']: row['count'] for row in rows}


def get_response_time_by_user():
    """Temps de réponse moyen par utilisateur"""
    with get_conn() as conn:
        rows = conn.execute("""
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
        """).fetchall()

    return [(row['matricule'], row['avg_time'], row['response_count'],
             row['min_time'], row['max_time']) for row in rows]