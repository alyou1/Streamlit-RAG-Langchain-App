import streamlit as st
import pandas as pd
from auth import logout_user, register_user, get_connection, hash_password

# ===============================
# 🔒 Vérification accès admin
# ===============================
if "logged_in" not in st.session_state or not st.session_state.logged_in:
    st.error("🚫 Accès refusé. Veuillez vous connecter.")
    if st.button("🔑 Retour à la connexion"):
        st.switch_page("app.py")
    st.stop()

if st.session_state.role != "admin":
    st.error("🚫 Accès refusé. Page réservée aux admins.")
    st.stop()


# ===============================
# 🎨 Style CSS personnalisé
# ===============================
st.markdown("""
    <style>
        .title {
            font-size: 28px;
            font-weight: bold;
            color: #2C3E50;
        }
        .card {
            padding: 20px;
            border-radius: 12px;
            background: #f9f9f9;
            box-shadow: 0 4px 8px rgba(0,0,0,0.05);
            margin-bottom: 15px;
        }
        .success {
            color: #27ae60;
            font-weight: bold;
        }
        .warning {
            color: #e67e22;
            font-weight: bold;
        }
    </style>
""", unsafe_allow_html=True)

# ===============================
# 🏠 Header
# ===============================
st.markdown("<div class='title'>👑 Tableau de bord Administrateur</div>", unsafe_allow_html=True)
st.write(f"Bienvenue **{st.session_state.nom} {st.session_state.prenom}** ✨")

with st.sidebar:
    if st.button("🔓 Déconnexion"):
        logout_user()
        st.rerun()
# ===============================
# ➕ Création utilisateur
# ===============================
with st.expander("➕ Créer un nouvel utilisateur", expanded=False):
    with st.form("create_user_form"):
        col1, col2 = st.columns(2)
        with col1:
            matricule = st.text_input("Matricule")
            nom = st.text_input("Nom")
            prenom = st.text_input("Prénom")
        with col2:
            email = st.text_input("Email")
            password = st.text_input("Mot de passe", type="password")
            role = st.selectbox("Rôle", ["juridique", "admin", "rh"])
        submitted = st.form_submit_button("✅ Créer l’utilisateur")

        if submitted:
            try:
                register_user(matricule, nom, prenom, email, password, role)
                st.success(f"✅ Utilisateur **{nom} {prenom}** créé avec succès ({role})")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Erreur : {e}")

# ===============================
# 📋 Liste des utilisateurs
# ===============================
st.subheader("📋 Gestion des utilisateurs")

conn = get_connection()
cursor = conn.execute("SELECT matricule, nom, prenom, email, role FROM users")
users = cursor.fetchall()
conn.close()

if users:
    df = pd.DataFrame(users, columns=["Matricule", "Nom", "Prénom", "Email", "Rôle"])

    # 🔎 Filtres
    col1, col2 = st.columns([2, 1])
    with col1:
        search = st.text_input("🔎 Rechercher par nom, prénom ou email")
    with col2:
        role_filter = st.selectbox("🎭 Filtrer par rôle", ["Tous", "juridique", "admin", "rh"])

    df_filtered = df.copy()
    if search:
        df_filtered = df_filtered[df_filtered.apply(lambda row: search.lower() in row.astype(str).str.lower().to_string(), axis=1)]
    if role_filter != "Tous":
        df_filtered = df_filtered[df_filtered["Rôle"] == role_filter]

    # 📊 Tableau filtré
    st.dataframe(df_filtered, use_container_width=True, hide_index=True)

    st.markdown("---")
    col1, col2 = st.columns(2)

    # 🗑️ Supprimer
    with col1:
        selected_rows = st.multiselect("Sélectionnez des matricules à supprimer", df_filtered["Matricule"])
        if st.button("🗑️ Supprimer sélection"):
            if selected_rows:
                conn = get_connection()
                for mat in selected_rows:
                    conn.execute("DELETE FROM users WHERE matricule = ?", (mat,))
                conn.commit()
                conn.close()
                st.success("✅ Utilisateur(s) supprimé(s) avec succès")
                st.rerun()
            else:
                st.warning("⚠️ Veuillez sélectionner au moins un utilisateur")

    # ✏️ Modifier
    with col2:
        st.subheader("✏️ Modifier un utilisateur")
        if not df_filtered.empty:
            user_to_modify = st.selectbox("Choisir l’utilisateur", df_filtered["Matricule"])
            new_password = st.text_input("Nouveau mot de passe (optionnel)", type="password", key="edit_pass")
            new_role = st.selectbox("Nouveau rôle", ["juridique", "admin", "rh"], key="edit_role")

            if st.button("💾 Sauvegarder les modifications"):
                conn = get_connection()
                query_parts, params = [], []
                if new_password:
                    query_parts.append("password = ?")
                    params.append(hash_password(new_password))
                if new_role:
                    query_parts.append("role = ?")
                    params.append(new_role)

                if query_parts:
                    params.append(user_to_modify)
                    query = f"UPDATE users SET {', '.join(query_parts)} WHERE matricule = ?"
                    conn.execute(query, tuple(params))
                    conn.commit()
                    conn.close()
                    st.success("✅ Modifications appliquées avec succès")
                    st.rerun()
                else:
                    st.warning("⚠️ Aucune modification détectée")

else:
    st.info("ℹ️ Aucun utilisateur enregistré.")
