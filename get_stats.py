import sqlite3
from contextlib import contextmanager
import datetime
DB_PATH = "users.db"

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.commit()
    conn.close()

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
            SELECT 
                feedback_type,
                COUNT(*) as count
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
        # Total messages par utilisateur
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

        # Feedbacks par utilisateur
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

    # Combiner les stats
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
                conv_name,
                matricule,
                COUNT(*) as message_count,
                MIN(timestamp) as created_at,
                MAX(timestamp) as last_message_at
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
            SELECT DISTINCT 
                c.matricule,
                MAX(c.timestamp) as last_activity
            FROM conversations c
            GROUP BY c.matricule
            ORDER BY last_activity DESC
        """).fetchall()

    return [(row['matricule'], row['last_activity']) for row in rows]
