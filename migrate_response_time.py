import sqlite3

DB_PATH = "users.db"


def migrate_add_response_time():
    """
    Ajoute la colonne response_time à la table conversations si elle n'existe pas
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Vérifier si la colonne existe déjà
        cursor.execute("PRAGMA table_info(conversations)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'response_time' not in columns:
            print("📝 Ajout de la colonne 'response_time' à la table conversations...")
            cursor.execute("""
                ALTER TABLE conversations 
                ADD COLUMN response_time REAL
            """)
            conn.commit()
            print("✅ Colonne 'response_time' ajoutée avec succès !")
        else:
            print("✅ La colonne 'response_time' existe déjà.")

        # Afficher les statistiques
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(response_time) as with_time,
                AVG(response_time) as avg_time
            FROM conversations
            WHERE role = 'assistant'
        """)

        stats = cursor.fetchone()
        print(f"\n📊 Statistiques:")
        print(f"   Total réponses assistant : {stats[0]}")
        print(f"   Avec temps de réponse : {stats[1]}")
        print(f"   Temps moyen : {stats[2]:.2f}s" if stats[2] else "   Temps moyen : N/A")

    except Exception as e:
        print(f"❌ Erreur lors de la migration : {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    print("🚀 Migration de la base de données")
    print("=" * 50)
    migrate_add_response_time()
    print("\n✅ Migration terminée !")