import streamlit as st
from auth import logout_user, register_user, get_connection, hash_password

# Vérification de l’accès admin
if "logged_in" not in st.session_state or not st.session_state.logged_in:
    st.error("🚫 Accès refusé. Veuillez vous connecter.")
    if st.button("🔑 Retour à la connexion"):
        st.switch_page("app.py")
    st.stop()

if st.session_state.role != "admin":
    st.error("🚫 Accès refusé. Page réservée aux admins.")
    st.stop()

st.title("👑 Interface Admin")
st.write(f"Bienvenue, {st.session_state.nom} {st.session_state.prenom} !")

# --- Déconnexion ---
if st.button("🔓 Se déconnecter"):
    logout_user()
    st.rerun()

st.markdown("---")

# --- Créer un nouvel utilisateur ---
st.subheader("➕ Créer un nouvel utilisateur")
with st.form("create_user_form"):
    matricule = st.text_input("Matricule")
    nom = st.text_input("Nom")
    prenom = st.text_input("Prénom")
    email = st.text_input("Email")
    password = st.text_input("Mot de passe", type="password")
    role = st.selectbox("Rôle", ["user", "admin"])
    submitted = st.form_submit_button("Créer l’utilisateur")

    if submitted:
        try:
            register_user(matricule, nom, prenom, email, password, role)
            st.success(f"✅ Utilisateur {nom} {prenom} créé avec succès ({role})")
        except Exception as e:
            st.error(f"❌ Erreur : {e}")

st.markdown("---")

# --- Liste des utilisateurs ---
st.subheader("📋 Gestion des utilisateurs existants")
conn = get_connection()
cursor = conn.execute("SELECT matricule, nom, prenom, email, role FROM users")
users = cursor.fetchall()
conn.close()

if users:
    import pandas as pd
    df = pd.DataFrame(users, columns=["Matricule", "Nom", "Prénom", "Email", "Rôle"])
    selected_rows = st.multiselect("Sélectionnez un ou plusieurs utilisateurs", df["Matricule"])

    # --- Supprimer utilisateur ---
    if st.button("🗑️ Supprimer l’utilisateur(s) sélectionné(s)"):
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

    st.markdown("---")

    # --- Modifier mot de passe ---
    st.subheader("🔑 Modifier le mot de passe d’un utilisateur")
    user_to_modify = st.selectbox("Choisir l’utilisateur", df["Matricule"])
    new_password = st.text_input("Nouveau mot de passe", type="password")
    if st.button("Modifier le mot de passe"):
        if new_password:
            conn = get_connection()
            conn.execute("UPDATE users SET password = ? WHERE matricule = ?", (hash_password(new_password), user_to_modify))
            conn.commit()
            conn.close()
            st.success("✅ Mot de passe modifié avec succès")
            st.rerun()
        else:
            st.warning("⚠️ Veuillez entrer un nouveau mot de passe")

else:
    st.info("Aucun utilisateur enregistré.")
