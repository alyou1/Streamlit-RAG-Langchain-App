import sqlite3
import sys

DB_PATH = "users.db"


def check_database():
    """Vérifie que la base de données est correctement configurée"""
    print("🔍 Vérification de la base de données")
    print("=" * 60)

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 1. Vérifier que la table conversations existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='conversations'")
        if cursor.fetchone():
            print("✅ Table 'conversations' existe")
        else:
            print("❌ Table 'conversations' n'existe pas")
            return False

        # 2. Vérifier que la colonne response_time existe
        cursor.execute("PRAGMA table_info(conversations)")
        columns = {column[1]: column[2] for column in cursor.fetchall()}

        if 'response_time' in columns:
            print(f"✅ Colonne 'response_time' existe (type: {columns['response_time']})")
        else:
            print("❌ Colonne 'response_time' n'existe pas")
            print("\n💡 Solution : Exécutez le script de migration:")
            print("   python migrate_response_time.py")
            return False

        # 3. Vérifier s'il y a des données avec response_time
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(response_time) as with_time
            FROM conversations
            WHERE role = 'assistant'
        """)

        total, with_time = cursor.fetchone()
        print(f"\n📊 Statistiques:")
        print(f"   Total réponses assistant : {total}")
        print(f"   Avec temps de réponse : {with_time}")

        if with_time == 0 and total > 0:
            print("\n⚠️  Vous avez des réponses mais aucun temps enregistré")
            print("   → Les nouveaux messages enregistreront le temps de réponse")
        elif with_time > 0:
            cursor.execute("""
                SELECT AVG(response_time) as avg_time
                FROM conversations
                WHERE role = 'assistant' AND response_time IS NOT NULL
            """)
            avg_time = cursor.fetchone()[0]
            print(f"   Temps moyen : {avg_time:.2f}s")

        conn.close()
        return True

    except Exception as e:
        print(f"❌ Erreur : {e}")
        return False


def check_get_stats():
    """Vérifie que get_stats.py a les nouvelles fonctions"""
    print("\n🔍 Vérification de get_stats.py")
    print("=" * 60)

    try:
        from get_stats import (
            get_average_response_time,
            get_response_time_by_day,
            get_response_time_distribution,
            get_response_time_by_user
        )
        print("✅ Toutes les fonctions de temps de réponse sont disponibles")
        return True
    except ImportError as e:
        print(f"❌ Fonctions manquantes dans get_stats.py")
        print(f"   Erreur: {e}")
        print("\n💡 Solution : Ajoutez ces fonctions dans get_stats.py:")
        print("   - get_average_response_time()")
        print("   - get_response_time_by_day()")
        print("   - get_response_time_distribution()")
        print("   - get_response_time_by_user()")
        return False


def check_chat():
    """Vérifie que le chat enregistre les temps de réponse"""
    print("\n🔍 Vérification du code du chat")
    print("=" * 60)

    try:
        with open("pages/chat.py", "r") as f:
            content = f.read()

        checks = [
            ("import time", "Import du module time"),
            ("start_time = time.time()", "Capture du temps de début"),
            ("end_time = time.time()", "Capture du temps de fin"),
            ("response_time", "Calcul du temps de réponse"),
            ("save_message(matricule, current_conv_name, \"assistant\", response, response_time)",
             "Sauvegarde avec temps de réponse")
        ]

        all_ok = True
        for check_str, description in checks:
            if check_str in content:
                print(f"✅ {description}")
            else:
                print(f"❌ {description} - Non trouvé")
                all_ok = False

        return all_ok

    except FileNotFoundError:
        print("❌ Fichier pages/chat.py non trouvé")
        return False
    except Exception as e:
        print(f"❌ Erreur : {e}")
        return False


if __name__ == "__main__":
    print("\n🚀 Vérification de l'installation - Temps de réponse")
    print("=" * 60)

    db_ok = check_database()
    stats_ok = check_get_stats()
    chat_ok = check_chat()

    print("\n" + "=" * 60)
    print("📋 RÉSUMÉ")
    print("=" * 60)
    print(f"Base de données : {'✅ OK' if db_ok else '❌ Problème'}")
    print(f"Fonctions stats : {'✅ OK' if stats_ok else '❌ Problème'}")
    print(f"Code du chat    : {'✅ OK' if chat_ok else '❌ Problème'}")

    if db_ok and stats_ok and chat_ok:
        print("\n🎉 Tout est prêt ! Vous pouvez utiliser les statistiques de temps de réponse.")
    else:
        print("\n⚠️  Des problèmes ont été détectés. Suivez les solutions indiquées ci-dessus.")

    print()