import sqlite3
import psycopg2
from dotenv import load_dotenv
import os
import sys

load_dotenv()


def check_sqlite_db():
    """Vérifie l'existence et le contenu de la base SQLite"""
    # Chemins possibles pour users.db
    possible_paths = [
        "users.db",
        "../users.db",
        "./users.db",
        os.path.join(os.path.dirname(__file__), "users.db"),
        os.path.join(os.path.dirname(__file__), "..", "users.db"),
    ]

    print("🔍 Recherche de users.db...")

    sqlite_path = None
    for path in possible_paths:
        if os.path.exists(path):
            print(f"✅ Trouvé : {os.path.abspath(path)}")
            sqlite_path = path
            break

    if not sqlite_path:
        print("❌ Fichier users.db introuvable dans les chemins suivants :")
        for path in possible_paths:
            print(f"   - {os.path.abspath(path)}")
        print("\n💡 Solution : Spécifiez le chemin complet de votre fichier users.db")
        custom_path = input("Entrez le chemin vers users.db (ou 'q' pour quitter) : ")

        if custom_path.lower() == 'q':
            sys.exit(1)

        if os.path.exists(custom_path):
            sqlite_path = custom_path
        else:
            print(f"❌ Le fichier {custom_path} n'existe pas")
            sys.exit(1)

    # Vérifier les tables
    print(f"\n📊 Analyse de la base : {sqlite_path}")
    conn = sqlite3.connect(sqlite_path)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()

    if not tables:
        print("❌ La base SQLite est vide (aucune table)")
        conn.close()
        sys.exit(1)

    print(f"✅ Tables trouvées : {[t[0] for t in tables]}")

    # Compter les enregistrements
    stats = {}
    for table_name in [t[0] for t in tables]:
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        stats[table_name] = count
        print(f"   - {table_name}: {count} enregistrement(s)")

    conn.close()

    if stats.get('users', 0) == 0:
        print("\n⚠️ Attention : La table 'users' existe mais est vide")
        response = input("Voulez-vous continuer quand même ? (o/n) : ")
        if response.lower() != 'o':
            sys.exit(1)

    return sqlite_path


def migrate_data(sqlite_path):
    """Migre les données de SQLite vers PostgreSQL"""

    # Connexion SQLite
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_cursor = sqlite_conn.cursor()

    # Connexion PostgreSQL
    try:
        pg_conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST"),
            port=os.getenv("POSTGRES_PORT"),
            database=os.getenv("POSTGRES_DB"),
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD")
        )
        pg_cursor = pg_conn.cursor()
        print("✅ Connexion PostgreSQL établie")
    except Exception as e:
        print(f"❌ Erreur de connexion PostgreSQL : {e}")
        print("\n💡 Vérifiez votre fichier .env :")
        print(f"   POSTGRES_HOST={os.getenv('POSTGRES_HOST')}")
        print(f"   POSTGRES_PORT={os.getenv('POSTGRES_PORT')}")
        print(f"   POSTGRES_DB={os.getenv('POSTGRES_DB')}")
        print(f"   POSTGRES_USER={os.getenv('POSTGRES_USER')}")
        sys.exit(1)

    print("\n🔄 Début de la migration...\n")

    # Récupérer la liste des tables SQLite
    sqlite_cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    available_tables = [t[0] for t in sqlite_cursor.fetchall()]

    # 1. Migrer users
    if 'users' in available_tables:
        print("📋 Migration de la table 'users'...")
        sqlite_cursor.execute("SELECT matricule, nom, prenom, email, password, role FROM users")
        users = sqlite_cursor.fetchall()

        migrated = 0
        for user in users:
            try:
                pg_cursor.execute("""
                    INSERT INTO users (matricule, nom, prenom, email, password, role)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (matricule) DO NOTHING
                """, user)
                migrated += 1
            except Exception as e:
                print(f"⚠️ Erreur user {user[0]}: {e}")

        pg_conn.commit()
        print(f"✅ {migrated}/{len(users)} utilisateurs migrés")
    else:
        print("⚠️ Table 'users' non trouvée, ignorée")

    # 2. Migrer user_sessions
    if 'user_sessions' in available_tables:
        print("\n📋 Migration de la table 'user_sessions'...")
        sqlite_cursor.execute("""
            SELECT matricule, login_time, last_activity, logout_time, is_active 
            FROM user_sessions
        """)
        sessions = sqlite_cursor.fetchall()

        migrated = 0
        for session in sessions:
            try:
                pg_cursor.execute("""
                    INSERT INTO user_sessions 
                    (matricule, login_time, last_activity, logout_time, is_active)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (matricule) DO UPDATE SET
                        login_time = EXCLUDED.login_time,
                        last_activity = EXCLUDED.last_activity,
                        logout_time = EXCLUDED.logout_time,
                        is_active = EXCLUDED.is_active
                """, session)
                migrated += 1
            except Exception as e:
                print(f"⚠️ Erreur session {session[0]}: {e}")

        pg_conn.commit()
        print(f"✅ {migrated}/{len(sessions)} sessions migrées")
    else:
        print("⚠️ Table 'user_sessions' non trouvée, ignorée")

    # 3. Migrer conversations
    if 'conversations' in available_tables:
        print("\n📋 Migration de la table 'conversations'...")
        sqlite_cursor.execute("""
            SELECT matricule, conv_name, role, content, timestamp, response_time
            FROM conversations
        """)
        conversations = sqlite_cursor.fetchall()

        migrated = 0
        batch_size = 100
        for i in range(0, len(conversations), batch_size):
            batch = conversations[i:i + batch_size]
            for conv in batch:
                try:
                    pg_cursor.execute("""
                        INSERT INTO conversations 
                        (matricule, conv_name, role, content, timestamp, response_time)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, conv)
                    migrated += 1
                except Exception as e:
                    print(f"⚠️ Erreur conversation: {e}")

            pg_conn.commit()
            print(f"   Progression : {min(i + batch_size, len(conversations))}/{len(conversations)}")

        print(f"✅ {migrated}/{len(conversations)} conversations migrées")
    else:
        print("⚠️ Table 'conversations' non trouvée, ignorée")

    # 4. Migrer message_feedback
    if 'message_feedback' in available_tables:
        print("\n📋 Migration de la table 'message_feedback'...")
        sqlite_cursor.execute("""
            SELECT matricule, conversation_name, message_index, feedback_type, timestamp
            FROM message_feedback
        """)
        feedbacks = sqlite_cursor.fetchall()

        migrated = 0
        for feedback in feedbacks:
            try:
                pg_cursor.execute("""
                    INSERT INTO message_feedback 
                    (matricule, conversation_name, message_index, feedback_type, timestamp)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (matricule, conversation_name, message_index) DO NOTHING
                """, feedback)
                migrated += 1
            except Exception as e:
                print(f"⚠️ Erreur feedback: {e}")

        pg_conn.commit()
        print(f"✅ {migrated}/{len(feedbacks)} feedbacks migrés")
    else:
        print("⚠️ Table 'message_feedback' non trouvée, ignorée")

    # Fermeture des connexions
    sqlite_cursor.close()
    sqlite_conn.close()
    pg_cursor.close()
    pg_conn.close()

    print("\n" + "=" * 60)
    print("🎉 Migration terminée avec succès!")
    print("=" * 60)

    # Afficher un résumé
    print("\n📊 Résumé de la migration :")
    pg_conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        database=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD")
    )
    pg_cursor = pg_conn.cursor()

    for table in ['users', 'user_sessions', 'conversations', 'message_feedback']:
        pg_cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = pg_cursor.fetchone()[0]
        print(f"   - {table}: {count} enregistrement(s)")

    pg_cursor.close()
    pg_conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("🔄 MIGRATION SQLite → PostgreSQL")
    print("=" * 60 + "\n")

    # Vérifier la base SQLite
    sqlite_path = check_sqlite_db()

    print("\n" + "=" * 60)
    response = input("\n▶️  Lancer la migration maintenant ? (o/n) : ")

    if response.lower() == 'o':
        migrate_data(sqlite_path)
    else:
        print("❌ Migration annulée")
        sys.exit(0)
