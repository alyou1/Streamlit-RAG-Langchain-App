import streamlit as st
from auth import check_and_restore_session, logout_user, update_user_password
import time

# ===============================
# 🔒 Vérification de la session
# ===============================

check_and_restore_session()

if "logged_in" not in st.session_state or not st.session_state.logged_in:
    st.error("🚫 Accès refusé. Veuillez vous connecter.")
    if st.button("🔑 Retour à la connexion"):
        st.switch_page("app.py")
    st.stop()

# ===============================
# 🎨 Configuration de la page
# ===============================

st.set_page_config(
    page_title="Modifier mon mot de passe - SGCI",
    page_icon="🔑",
    layout="centered"
)

# CSS personnalisé
st.markdown("""
    <style>
    .stButton>button {
        width: 100%;
        background-color: #E60028;
        color: white;
        font-weight: bold;
        border-radius: 5px;
        padding: 0.75rem;
        border: none;
        transition: all 0.3s ease;
    }

    .stButton>button:hover {
        background-color: #cc0022;
        box-shadow: 0 4px 8px rgba(230, 0, 40, 0.3);
    }

    .header-section {
        text-align: center;
        padding: 1rem;
        background: linear-gradient(135deg, #E60028 0%, #cc0022 100%);
        color: white;
        border-radius: 10px;
        margin-bottom: 2rem;
    }

    .info-box {
        padding: 1rem;
        background-color: #f0f2f6;
        border-radius: 8px;
        margin-bottom: 1rem;
    }
    </style>
""", unsafe_allow_html=True)

# ===============================
# 📱 Sidebar
# ===============================

with st.sidebar:

    # Navigation selon le rôle
    if st.session_state.role == "admin":
        if st.button("⚙️ Administration", use_container_width=True):
            st.switch_page("pages/admin.py")

    if st.button("🔓 Logout", use_container_width=True, type="primary"):
        logout_user()
        st.rerun()

# ===============================
# 🔑 Page principale
# ===============================

st.markdown("""
    <div class="header-section">
        <h2>🔑 Modifier mon mot de passe</h2>
    </div>
""", unsafe_allow_html=True)

st.markdown(f"""
    <div class="info-box">
        <strong>👤 Compte :</strong> {st.session_state.prenom} {st.session_state.nom}<br>
        <strong>📧 Email :</strong> {st.session_state.email}<br>
        <strong>🆔 Matricule :</strong> {st.session_state.matricule}
    </div>
""", unsafe_allow_html=True)

st.markdown("---")

# Formulaire de changement de mot de passe
st.markdown("### 🔐 Nouveau mot de passe")

with st.form("change_password_form"):
    st.markdown("**Remplissez tous les champs ci-dessous**")

    old_password = st.text_input(
        "Ancien mot de passe *",
        type="password",
        placeholder="••••••••",
        help="Votre mot de passe actuel"
    )

    new_password = st.text_input(
        "Nouveau mot de passe *",
        type="password",
        placeholder="••••••••",
        help="Minimum 4 caractères"
    )

    confirm_new_password = st.text_input(
        "Confirmer le nouveau mot de passe *",
        type="password",
        placeholder="••••••••",
        help="Retapez votre nouveau mot de passe"
    )

    st.markdown("---")

    # Conseils de sécurité
    with st.expander("💡 Conseils pour un mot de passe sécurisé"):
        st.markdown("""
        - **Minimum 6 caractères** (8 recommandé)
        - Combinez **lettres majuscules et minuscules**
        - Ajoutez des **chiffres et caractères spéciaux**
        - Évitez les informations personnelles évidentes
        - N'utilisez **pas le même mot de passe** pour plusieurs comptes
        """)

    col1, col2 = st.columns(2)

    with col1:
        submit_button = st.form_submit_button("✅ Modifier le mot de passe", use_container_width=True, type="primary")

    with col2:
        cancel_button = st.form_submit_button("❌ Annuler", use_container_width=True)

    if cancel_button:
        st.switch_page("app.py")

    if submit_button:
        # Validation des champs
        if not old_password or not new_password or not confirm_new_password:
            st.error("❌ Tous les champs sont obligatoires")
        elif len(new_password) < 4:
            st.error("❌ Le nouveau mot de passe doit contenir au moins 4 caractères")
        elif new_password != confirm_new_password:
            st.error("❌ Les nouveaux mots de passe ne correspondent pas")
        elif old_password == new_password:
            st.warning("⚠️ Le nouveau mot de passe doit être différent de l'ancien")
        else:
            # Tentative de modification
            with st.spinner("🔄 Modification en cours..."):
                time.sleep(0.5)

                success, message = update_user_password(
                    st.session_state.matricule,
                    old_password,
                    new_password
                )

                if success:
                    st.success(f"✅ {message}")
                    st.info("👉 Vous allez être déconnecté. Reconnectez-vous avec votre nouveau mot de passe.")
                    time.sleep(3)
                    logout_user()
                    st.switch_page("app.py")
                else:
                    st.error(f"❌ {message}")

# Informations de sécurité
st.markdown("---")
st.markdown("""
    <div style="text-align: center; color: #666; font-size: 0.85rem;">
        🔒 <strong>Sécurité</strong> : Votre mot de passe est chiffré et stocké de manière sécurisée.<br>
        Personne, y compris les administrateurs, ne peut voir votre mot de passe en clair.
    </div>
""", unsafe_allow_html=True)
