import sqlite3

DB_PATH = "users.db"


def test_sessions():
    """Script pour tester et débugger les sessions"""

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    print("\n" + "=" * 60)
    print("📊 ÉTAT DES SESSIONS")
    print("=" * 60)

    # Toutes les sessions
    all_sessions = conn.execute("""
        SELECT s.matricule, u.nom, u.prenom, s.login_time, s.logout_time, s.is_active
        FROM user_sessions s
        JOIN users u ON s.matricule = u.matricule
        ORDER BY s.login_time DESC
    """).fetchall()

    print(f"\n📋 Total sessions dans la base : {len(all_sessions)}")
    print("-" * 60)

    for session in all_sessions:
        status = "🟢 CONNECTÉ" if session['is_active'] == 1 else "🔴 DÉCONNECTÉ"
        print(f"\n{status}")
        print(f"   Matricule : {session['matricule']}")
        print(f"   Nom       : {session['nom']} {session['prenom']}")
        print(f"   Login     : {session['login_time']}")
        print(f"   Logout    : {session['logout_time'] or 'N/A'}")
        print(f"   is_active : {session['is_active']}")

    # Statistiques
    active_count = conn.execute("""
        SELECT COUNT(*) as count FROM user_sessions WHERE is_active = 1
    """).fetchone()['count']

    inactive_count = conn.execute("""
        SELECT COUNT(*) as count FROM user_sessions WHERE is_active = 0
    """).fetchone()['count']

    print("\n" + "=" * 60)
    print("📈 STATISTIQUES")
    print("=" * 60)
    print(f"🟢 Utilisateurs connectés    : {active_count}")
    print(f"🔴 Utilisateurs déconnectés  : {inactive_count}")
    print(f"📊 Total                     : {len(all_sessions)}")

    conn.close()


def reset_all_sessions():
    """Déconnecter tous les utilisateurs (pour debug)"""
    conn = sqlite3.connect(DB_PATH)

    count = conn.execute("""
        UPDATE user_sessions 
        SET is_active = 0, logout_time = datetime('now')
        WHERE is_active = 1
    """).rowcount

    conn.commit()
    conn.close()

    print(f"\n✅ {count} session(s) déconnectée(s)")


def clean_duplicate_sessions():
    """Nettoyer les éventuels doublons (garde seulement la dernière session)"""
    conn = sqlite3.connect(DB_PATH)

    # Cette requête ne devrait rien faire si tout va bien
    # Car matricule est PRIMARY KEY
    result = conn.execute("""
        SELECT matricule, COUNT(*) as count
        FROM user_sessions
        GROUP BY matricule
        HAVING count > 1
    """).fetchall()

    if result:
        print(f"\n⚠️ DOUBLONS DÉTECTÉS :")
        for row in result:
            print(f"   {row[0]} : {row[1]} sessions")

        print("\n❌ ERREUR : Il ne devrait pas y avoir de doublons avec PRIMARY KEY")
        print("   Vérifiez votre structure de table user_sessions")
    else:
        print("\n✅ Aucun doublon détecté")

    conn.close()


if __name__ == "__main__":
    import sys

    print("\n🔍 TEST DES SESSIONS UTILISATEURS")
    print("=" * 60)

    if len(sys.argv) > 1:
        if sys.argv[1] == "reset":
            reset_all_sessions()
        elif sys.argv[1] == "clean":
            clean_duplicate_sessions()

    test_sessions()

    print("\n💡 COMMANDES DISPONIBLES :")
    print("   python test_sessions.py          # Afficher l'état")
    print("   python test_sessions.py reset    # Déconnecter tout le monde")
    print("   python test_sessions.py clean    # Vérifier les doublons")
    print("")