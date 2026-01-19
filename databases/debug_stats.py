"""
Script de diagnostic pour vérifier les données de temps de réponse
Exécutez ce script pour identifier le problème
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": os.getenv("POSTGRES_PORT", "5432"),
    "database": os.getenv("POSTGRES_DB"),
    "user": os.getenv("POSTGRES_USER"),
    "password": os.getenv("POSTGRES_PASSWORD")
}

print("="*60)
print("🔍 DIAGNOSTIC - Temps de réponse")
print("="*60)

try:
    # Connexion
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    print("✅ Connexion PostgreSQL établie\n")

    # 1. Vérifier la structure de la table
    print("📋 Structure de la table 'conversations':")
    cursor.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'conversations'
        ORDER BY ordinal_position
    """)
    columns = cursor.fetchall()
    for col in columns:
        print(f"   - {col['column_name']}: {col['data_type']}")

    print("\n" + "-"*60)

    # 2. Compter les conversations totales
    cursor.execute("SELECT COUNT(*) as count FROM conversations")
    total = cursor.fetchone()['count']
    print(f"\n📊 Total conversations: {total}")

    # 3. Compter les réponses avec response_time
    cursor.execute("""
        SELECT COUNT(*) as count 
        FROM conversations 
        WHERE role = 'assistant' AND response_time IS NOT NULL
    """)
    with_time = cursor.fetchone()['count']
    print(f"⏱️  Réponses avec response_time: {with_time}")

    # 4. Compter les réponses sans response_time
    cursor.execute("""
        SELECT COUNT(*) as count 
        FROM conversations 
        WHERE role = 'assistant' AND response_time IS NULL
    """)
    without_time = cursor.fetchone()['count']
    print(f"❌ Réponses sans response_time: {without_time}")

    print("\n" + "-"*60)

    # 5. Afficher quelques exemples
    if with_time > 0:
        print("\n📝 Exemples de données (5 dernières réponses avec temps):")
        cursor.execute("""
            SELECT matricule, timestamp, response_time, LEFT(content, 50) as preview
            FROM conversations 
            WHERE role = 'assistant' AND response_time IS NOT NULL
            ORDER BY timestamp DESC
            LIMIT 5
        """)
        examples = cursor.fetchall()
        for i, ex in enumerate(examples, 1):
            print(f"\n   {i}. Matricule: {ex['matricule']}")
            print(f"      Timestamp: {ex['timestamp']}")
            print(f"      Response time: {ex['response_time']}s")
            print(f"      Aperçu: {ex['preview']}...")

    print("\n" + "-"*60)

    # 6. Tester get_response_time_by_day()
    print("\n🧪 Test de get_response_time_by_day():")
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

    if rows:
        print(f"   ✅ {len(rows)} jours avec données")
        print("\n   Aperçu des 3 premiers jours:")
        for i, row in enumerate(rows[:3], 1):
            print(f"      {i}. Date: {row['date']}, Temps: {row['avg_time']:.2f}s, Réponses: {row['response_count']}")
    else:
        print("   ❌ Aucune donnée trouvée")
        print("   💡 Raison possible: Pas de conversations dans les 30 derniers jours")

    print("\n" + "-"*60)

    # 7. Tester get_response_time_distribution()
    print("\n🧪 Test de get_response_time_distribution():")
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
    distribution = cursor.fetchall()

    if distribution:
        print(f"   ✅ {len(distribution)} tranches avec données")
        for dist in distribution:
            print(f"      - {dist['time_range']}: {dist['count']} réponses")
    else:
        print("   ❌ Aucune donnée de distribution")

    print("\n" + "-"*60)

    # 8. Tester get_response_time_by_user()
    print("\n🧪 Test de get_response_time_by_user():")
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
        LIMIT 5
    """)
    by_user = cursor.fetchall()

    if by_user:
        print(f"   ✅ {len(by_user)} utilisateurs avec données")
        print("\n   Top 5 utilisateurs:")
        for i, user in enumerate(by_user, 1):
            print(f"      {i}. {user['matricule']}: {user['avg_time']:.2f}s (min: {user['min_time']:.2f}s, max: {user['max_time']:.2f}s)")
    else:
        print("   ❌ Aucune donnée par utilisateur")

    cursor.close()
    conn.close()

    print("\n" + "="*60)
    print("✅ DIAGNOSTIC TERMINÉ")
    print("="*60)

    # Recommandations
    print("\n💡 RECOMMANDATIONS:")
    if with_time == 0:
        print("   ⚠️  Aucun temps de réponse enregistré")
        print("   → Posez quelques questions dans le chat pour générer des données")
        print("   → Vérifiez que chat.py enregistre bien response_time")
    elif len(rows) == 0:
        print("   ⚠️  Pas de données dans les 30 derniers jours")
        print("   → Les conversations sont peut-être plus anciennes")
        print("   → Posez de nouvelles questions pour générer des données récentes")
    else:
        print("   ✅ Les données semblent correctes")
        print("   → Si les graphiques ne s'affichent toujours pas:")
        print("      1. Vérifiez que plotly est installé: pip install plotly")
        print("      2. Redémarrez Streamlit")
        print("      3. Vérifiez les erreurs dans la console Streamlit")

except Exception as e:
    print(f"\n❌ ERREUR: {e}")
    print("\n💡 Vérifiez votre fichier .env:")
    print(f"   POSTGRES_HOST={os.getenv('POSTGRES_HOST')}")
    print(f"   POSTGRES_PORT={os.getenv('POSTGRES_PORT')}")
    print(f"   POSTGRES_DB={os.getenv('POSTGRES_DB')}")
    print(f"   POSTGRES_USER={os.getenv('POSTGRES_USER')}")
