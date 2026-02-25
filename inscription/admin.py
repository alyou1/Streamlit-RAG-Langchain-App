import streamlit as st
import pandas as pd
from auth import logout_user, register_user, get_connection, hash_password, check_and_restore_session, \
    register_user_admin
from psycopg2.extras import RealDictCursor

# ===============================
# 🔒 Vérification accès admin
# ===============================

check_and_restore_session()

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
        .role-badge {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 5px;
            font-size: 12px;
            font-weight: bold;
        }
        .role-admin { background-color: #e74c3c; color: white; }
        .role-editeur { background-color: #3498db; color: white; }
        .role-user { background-color: #95a5a6; color: white; }
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
# 📊 Statistiques utilisateurs
# ===============================
with get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT role, COUNT(*) as count FROM users GROUP BY role")
    stats = cursor.fetchall()
    cursor.close()

stats_dict = {role: count for role, count in stats}

col1, col2, col3, col4, col5, col6 = st.columns(6)
with col1:
    st.metric("👑 Admins", stats_dict.get("admin", 0))
with col2:
    st.metric("✏️ Éditeurs RH", stats_dict.get("editeur_rh", 0))
with col3:
    st.metric("✏️ Éd. Juridique", stats_dict.get("editeur_juridique", 0))
with col4:
    st.metric("👔 Utilisateurs RH", stats_dict.get("rh", 0))
with col5:
    st.metric("⚖️ Util. Juridique", stats_dict.get("juridique", 0))
with col6:
    st.metric("👤 Users", stats_dict.get("user", 0))

st.divider()

# ===============================
# ➕ Création utilisateur
# ===============================
with st.expander("➕ Créer un nouvel utilisateur", expanded=False):
    st.markdown("### 📝 Informations de l'utilisateur")

    with st.form("create_user_form"):
        col1, col2 = st.columns(2)
        with col1:
            matricule = st.text_input("Matricule *", help="Identifiant unique de l'utilisateur")
            nom = st.text_input("Nom *")
            prenom = st.text_input("Prénom *")
        with col2:
            email = st.text_input("Email *")
            password = st.text_input("Mot de passe *", type="password", help="Minimum 6 caractères")
            role = st.selectbox(
                "Rôle *",
                [
                    "admin",
                    "editeur_rh",
                    "editeur_juridique",
                    "rh",
                    "juridique",
                    "user"
                ],
                help="Les éditeurs peuvent gérer les documents de leur département"
            )

        # Description des rôles
        role_descriptions = {
            "admin": "👑 **Admin** : Accès complet à tous les modules et documents",
            "editeur_rh": "✏️ **Éditeur RH** : Gestion des documents RH uniquement",
            "editeur_juridique": "✏️ **Éditeur Juridique** : Gestion des documents juridiques uniquement",
            "rh": "👔 **Utilisateur RH** : Consultation des documents RH uniquement",
            "juridique": "⚖️ **Utilisateur Juridique** : Consultation des documents juridiques uniquement",
            "user": "👤 **User** : Utilisateur standard (créé via inscription)"
        }

        st.info(role_descriptions.get(role, ""))

        submitted = st.form_submit_button("✅ Créer l'utilisateur", use_container_width=True)

        if submitted:
            # Validation des champs
            if not all([matricule, nom, prenom, email, password]):
                st.error("❌ Tous les champs sont obligatoires")
            elif len(password) < 6:
                st.error("❌ Le mot de passe doit contenir au moins 6 caractères")
            else:
                try:
                    register_user_admin(matricule, nom, prenom, email, password, role)
                    st.success(f"✅ Utilisateur **{nom} {prenom}** créé avec succès ({role})")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Erreur : {e}")

st.divider()

# ===============================
# 📋 Liste des utilisateurs
# ===============================
st.subheader("📋 Gestion des utilisateurs")

with get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT matricule, nom, prenom, email, role FROM users ORDER BY role, nom")
    users = cursor.fetchall()
    cursor.close()

if users:
    df = pd.DataFrame(users, columns=["Matricule", "Nom", "Prénom", "Email", "Rôle"])

    # 🔎 Filtres
    col1, col2, col3 = st.columns([3, 2, 2])
    with col1:
        search = st.text_input("🔎 Rechercher par nom, prénom ou email", key="search_users")
    with col2:
        role_filter = st.selectbox(
            "🎭 Filtrer par rôle",
            ["Tous", "admin", "editeur_rh", "editeur_juridique", "rh", "juridique", "user"],
            key="filter_role"
        )
    with col3:
        sort_option = st.selectbox(
            "📊 Trier par",
            ["Nom (A-Z)", "Nom (Z-A)", "Rôle", "Matricule"],
            key="sort_option"
        )

    # Application des filtres
    df_filtered = df.copy()

    if search:
        df_filtered = df_filtered[
            df_filtered["Nom"].str.contains(search, case=False, na=False) |
            df_filtered["Prénom"].str.contains(search, case=False, na=False) |
            df_filtered["Email"].str.contains(search, case=False, na=False)
            ]

    if role_filter != "Tous":
        df_filtered = df_filtered[df_filtered["Rôle"] == role_filter]

    # Tri
    if sort_option == "Nom (A-Z)":
        df_filtered = df_filtered.sort_values("Nom")
    elif sort_option == "Nom (Z-A)":
        df_filtered = df_filtered.sort_values("Nom", ascending=False)
    elif sort_option == "Rôle":
        df_filtered = df_filtered.sort_values("Rôle")
    elif sort_option == "Matricule":
        df_filtered = df_filtered.sort_values("Matricule")

    # Affichage du nombre de résultats
    st.caption(f"📊 {len(df_filtered)} utilisateur(s) affiché(s) sur {len(df)} total")


    # 📊 Tableau avec mise en forme
    def format_role(role):
        role_emoji = {
            "admin": "👑",
            "editeur_rh": "✏️",
            "editeur_juridique": "✏️",
            "rh": "👔",
            "juridique": "⚖️",
            "user": "👤"
        }
        return f"{role_emoji.get(role, '👤')} {role}"


    df_display = df_filtered.copy()
    df_display["Rôle"] = df_display["Rôle"].apply(format_role)

    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Matricule": st.column_config.TextColumn("Matricule", width="small"),
            "Nom": st.column_config.TextColumn("Nom", width="medium"),
            "Prénom": st.column_config.TextColumn("Prénom", width="medium"),
            "Email": st.column_config.TextColumn("Email", width="large"),
            "Rôle": st.column_config.TextColumn("Rôle", width="medium")
        }
    )

    st.markdown("---")

    # ===============================
    # 🗑️ SUPPRESSION ET ✏️ MODIFICATION
    # ===============================
    col1, col2 = st.columns(2)

    # 🗑️ Supprimer
    with col1:
        st.markdown("### 🗑️ Supprimer des utilisateurs")
        selected_rows = st.multiselect(
            "Sélectionnez des matricules à supprimer",
            df_filtered["Matricule"].tolist(),
            help="Vous pouvez sélectionner plusieurs utilisateurs"
        )

        if selected_rows:
            st.warning(f"⚠️ Vous êtes sur le point de supprimer **{len(selected_rows)}** utilisateur(s)")

            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("🗑️ Confirmer suppression", type="primary", use_container_width=True):
                    with get_connection() as conn:
                        cursor = conn.cursor()
                        for mat in selected_rows:
                            cursor.execute("DELETE FROM users WHERE matricule = %s", (mat,))
                        cursor.close()
                    st.success(f"✅ {len(selected_rows)} utilisateur(s) supprimé(s) avec succès")
                    st.rerun()
            with col_b:
                if st.button("❌ Annuler", use_container_width=True):
                    st.rerun()
        else:
            st.info("ℹ️ Sélectionnez au moins un utilisateur pour le supprimer")

    # ✏️ Modifier
    with col2:
        st.markdown("### ✏️ Modifier un utilisateur")

        if not df_filtered.empty:
            user_to_modify = st.selectbox(
                "Choisir l'utilisateur",
                df_filtered["Matricule"].tolist(),
                format_func=lambda
                    x: f"{x} - {df_filtered[df_filtered['Matricule'] == x]['Nom'].values[0]} {df_filtered[df_filtered['Matricule'] == x]['Prénom'].values[0]}"
            )

            # Récupération des infos actuelles
            current_user = df_filtered[df_filtered["Matricule"] == user_to_modify].iloc[0]

            # Extraire le rôle propre (sans emoji)
            current_role_clean = current_user['Rôle'].split()[-1]

            st.caption(
                f"**Utilisateur actuel :** {current_user['Nom']} {current_user['Prénom']} ({current_role_clean})")

            new_password = st.text_input(
                "Nouveau mot de passe (optionnel)",
                type="password",
                key="edit_pass",
                help="Laissez vide pour ne pas modifier"
            )

            roles_list = ["admin", "editeur_rh", "editeur_juridique", "rh", "juridique", "user"]
            current_role_index = roles_list.index(current_role_clean) if current_role_clean in roles_list else 0

            new_role = st.selectbox(
                "Nouveau rôle",
                roles_list,
                index=current_role_index,
                key="edit_role"
            )

            col_c, col_d = st.columns(2)
            with col_c:
                if st.button("💾 Sauvegarder", type="primary", use_container_width=True):
                    with get_connection() as conn:
                        cursor = conn.cursor()
                        query_parts, params = [], []

                        if new_password:
                            if len(new_password) < 6:
                                st.error("❌ Le mot de passe doit contenir au moins 6 caractères")
                            else:
                                query_parts.append("password = %s")
                                params.append(hash_password(new_password))

                        if new_role and new_role != current_role_clean:
                            query_parts.append("role = %s")
                            params.append(new_role)

                        if query_parts:
                            params.append(user_to_modify)
                            query = f"UPDATE users SET {', '.join(query_parts)} WHERE matricule = %s"
                            cursor.execute(query, tuple(params))
                            cursor.close()
                            st.success("✅ Modifications appliquées avec succès")
                            st.rerun()
                        else:
                            st.warning("⚠️ Aucune modification détectée")
                            cursor.close()
            with col_d:
                if st.button("❌ Annuler", use_container_width=True):
                    st.rerun()
        else:
            st.info("ℹ️ Aucun utilisateur à modifier")

else:
    st.info("ℹ️ Aucun utilisateur enregistré.")
    st.caption("👆 Utilisez la section ci-dessus pour créer votre premier utilisateur")

st.divider()

# ===============================
# 📈 Vue d'ensemble par département
# ===============================
st.subheader("📈 Vue d'ensemble par département")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("#### 👔 Département RH")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT role, COUNT(*) as count FROM users WHERE role IN ('editeur_rh', 'rh') GROUP BY role")
        rh_stats = cursor.fetchall()
        cursor.close()

    if rh_stats:
        for role, count in rh_stats:
            emoji = "✏️" if role == "editeur_rh" else "👤"
            st.metric(f"{emoji} {role}", count)
    else:
        st.info("Aucun utilisateur RH")

with col2:
    st.markdown("#### ⚖️ Département Juridique")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role, COUNT(*) as count FROM users WHERE role IN ('editeur_juridique', 'juridique') GROUP BY role")
        jur_stats = cursor.fetchall()
        cursor.close()

    if jur_stats:
        for role, count in jur_stats:
            emoji = "✏️" if role == "editeur_juridique" else "👤"
            st.metric(f"{emoji} {role}", count)
    else:
        st.info("Aucun utilisateur Juridique")

with col3:
    st.markdown("#### 👤 Utilisateurs Standards")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE role = 'user'")
        user_count = cursor.fetchone()[0]
        cursor.close()

    st.metric("👤 Users", user_count)