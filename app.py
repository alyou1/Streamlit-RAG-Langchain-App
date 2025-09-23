import streamlit as st
from auth import create_users_table, login_user, logout_user

# Création table si elle n'existe pas
create_users_table()

st.set_page_config(page_title="Chatbot", page_icon="🔐")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔐 Connexion")

    matricule = st.text_input("Matricule")
    password = st.text_input("Mot de passe", type="password")

    if st.button("Se connecter"):
        if login_user(matricule, password):
            st.success("✅ Connexion réussie")
            if st.session_state.role == "admin":
                st.switch_page("pages/admin.py")
            else:
                st.switch_page("pages/chat.py")
        else:
            st.error("❌ Identifiants incorrects")

    st.stop()

else:
    st.sidebar.success(f"Connecté en tant que {st.session_state.nom} {st.session_state.prenom}")
    st.markdown("""
    Utilise la bare laterale pour naviguer
    - ** Documents** : Pour charger et gérer vos documents.
    - ** Chat** : pour discuter avec l'assistant"""
    )
    if st.sidebar.button("Se déconnecter"):
        logout_user()
        st.rerun()
