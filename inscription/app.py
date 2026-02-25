"""
Application de Connexion Streamlit Améliorée
Avec gestion avancée de session, sécurité et UX optimisée + Inscription
"""

import streamlit as st
from auth import create_users_table, login_user, logout_user, check_and_restore_session, register_user
import time
from datetime import datetime
import re

# ==================== CONFIGURATION ====================

check_and_restore_session()

# Configuration de la page
st.set_page_config(
    page_title="Chatbot SGCI - Connexion",
    page_icon="🔐",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# CSS personnalisé pour améliorer le design
st.markdown("""
    <style>
    /* Styles pour le formulaire de connexion */
    .login-container {
        max-width: 400px;
        margin: 0 auto;
        padding: 2rem;
        background-color: #f8f9fa;
        border-radius: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }

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

    /* Amélioration des inputs */
    .stTextInput>div>div>input {
        border-radius: 5px;
        border: 2px solid #ddd;
        padding: 0.5rem;
    }

    .stTextInput>div>div>input:focus {
        border-color: #E60028;
        box-shadow: 0 0 0 0.2rem rgba(230, 0, 40, 0.25);
    }

    /* Message de bienvenue */
    .welcome-message {
        text-align: center;
        padding: 1rem;
        background: linear-gradient(135deg, #E60028 0%, #cc0022 100%);
        color: white;
        border-radius: 10px;
        margin-bottom: 1rem;
    }

    /* Sidebar user info */
    .user-info {
        padding: 1rem;
        background-color: #f0f2f6;
        border-radius: 8px;
        margin-bottom: 1rem;
    }

    /* Footer */
    .footer {
        text-align: center;
        color: #666;
        font-size: 0.85rem;
        padding: 1rem 0;
        margin-top: 2rem;
    }
    
    /* Tabs style */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem;
        justify-content: center;
    }
    
    .stTabs [data-baseweb="tab"] {
        padding: 0.5rem 2rem;
        font-weight: 600;
    }
    </style>
""", unsafe_allow_html=True)


# ==================== INITIALISATION ====================

# Initialisation de la session
def init_session_state():
    """Initialise tous les états de session nécessaires"""
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if "user_id" not in st.session_state:
        st.session_state.user_id = None

    if "matricule" not in st.session_state:
        st.session_state.matricule = None

    if "nom" not in st.session_state:
        st.session_state.nom = None

    if "prenom" not in st.session_state:
        st.session_state.prenom = None

    if "role" not in st.session_state:
        st.session_state.role = None

    if "login_attempts" not in st.session_state:
        st.session_state.login_attempts = 0

    if "last_login_attempt" not in st.session_state:
        st.session_state.last_login_attempt = None

    if "login_time" not in st.session_state:
        st.session_state.login_time = None


# Créer la table users si elle n'existe pas
try:
    create_users_table()
except Exception as e:
    st.error(f"❌ Erreur lors de l'initialisation de la base de données: {str(e)}")

# Initialiser la session
init_session_state()


# ==================== FONCTIONS UTILITAIRES ====================

def validate_matricule(matricule: str) -> bool:
    """Valide le format du matricule"""
    if not matricule:
        return False
    return len(matricule) >= 4


def validate_password(password: str) -> bool:
    """Valide le format du mot de passe"""
    if not password:
        return False
    return len(password) >= 4


def validate_email(email: str) -> bool:
    """Valide le format de l'email"""
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(email_pattern, email) is not None


def check_login_cooldown() -> tuple[bool, int]:
    """
    Vérifie si l'utilisateur doit attendre avant de réessayer
    Retourne (can_login, seconds_remaining)
    """
    if st.session_state.login_attempts >= 3:
        if st.session_state.last_login_attempt:
            elapsed = (datetime.now() - st.session_state.last_login_attempt).total_seconds()
            cooldown = 60  # 60 secondes de délai après 3 tentatives
            if elapsed < cooldown:
                return False, int(cooldown - elapsed)
            else:
                # Reset après le cooldown
                st.session_state.login_attempts = 0
                st.session_state.last_login_attempt = None
    return True, 0


def handle_login(matricule: str, password: str):
    """Gère le processus de connexion avec validations"""

    # Vérifier le cooldown
    can_login, seconds_remaining = check_login_cooldown()
    if not can_login:
        st.error(f"⏱️ Trop de tentatives. Veuillez attendre {seconds_remaining} secondes.")
        return

    # Validation des champs
    if not validate_matricule(matricule):
        st.warning("⚠️ Matricule invalide (minimum 4 caractères)")
        return

    if not validate_password(password):
        st.warning("⚠️ Mot de passe invalide (minimum 4 caractères)")
        return

    # Tentative de connexion
    with st.spinner("🔄 Connexion en cours..."):
        time.sleep(0.5)

        if login_user(matricule, password):
            # Succès
            st.session_state.login_attempts = 0
            st.session_state.last_login_attempt = None
            st.session_state.login_time = datetime.now()

            st.success(f"✅ Bienvenue {st.session_state.prenom} {st.session_state.nom} !")
            time.sleep(1)

            # Redirection selon le rôle
            if st.session_state.role == "admin":
                st.switch_page("pages/admin.py")
            else:
                st.switch_page("pages/chat.py")
        else:
            # Échec
            st.session_state.login_attempts += 1
            st.session_state.last_login_attempt = datetime.now()

            remaining_attempts = 3 - st.session_state.login_attempts
            if remaining_attempts > 0:
                st.error(f"❌ Identifiants incorrects. Tentatives restantes: {remaining_attempts}")
            else:
                st.error("🚫 Compte temporairement bloqué. Attendez 60 secondes.")


def handle_registration(matricule: str, nom: str, prenom: str, email: str, password: str, confirm_password: str):
    """Gère le processus d'inscription avec validations"""

    # Validation des champs
    if not matricule or not nom or not prenom or not email or not password or not confirm_password:
        st.warning("⚠️ Tous les champs sont obligatoires")
        return

    if not validate_matricule(matricule):
        st.warning("⚠️ Matricule invalide (minimum 4 caractères)")
        return

    if not nom.strip() or not prenom.strip():
        st.warning("⚠️ Le nom et le prénom ne peuvent pas être vides")
        return

    if not validate_email(email):
        st.warning("⚠️ Format d'email invalide")
        return

    if not validate_password(password):
        st.warning("⚠️ Mot de passe invalide (minimum 4 caractères)")
        return

    if password != confirm_password:
        st.error("❌ Les mots de passe ne correspondent pas")
        return

    # Tentative d'inscription
    with st.spinner("🔄 Création du compte en cours..."):
        time.sleep(0.5)

        success, message = register_user(matricule, nom, prenom, email, password)

        if success:
            st.success(f"✅ {message}")
            st.info("👉 Vous pouvez maintenant vous connecter avec vos identifiants")
            time.sleep(2)
            st.rerun()
        else:
            st.error(f"❌ {message}")


def handle_logout():
    """Gère la déconnexion"""
    with st.spinner("🔄 Déconnexion en cours..."):
        logout_user()
        time.sleep(0.5)
        st.success("✅ Déconnexion réussie")
        time.sleep(0.5)
        st.rerun()


# ==================== AFFICHAGE PRINCIPAL ====================

if not st.session_state.logged_in:
    # ========== PAGE DE CONNEXION/INSCRIPTION ==========
    st.markdown('<div class="welcome-message"><h2>🔐 Chatbot SGCI</h2></div>',
                unsafe_allow_html=True)

    # Tabs pour Connexion et Inscription
    tab1, tab2 = st.tabs(["🔑 Connexion", "✍️ Inscription"])

    # ========== TAB CONNEXION ==========
    with tab1:
        st.markdown("### 👤 Identifiez-vous")

        # Champs de saisie
        matricule_login = st.text_input(
            "Matricule",
            placeholder="Entrez votre matricule",
            help="Votre matricule d'employé SGCI",
            max_chars=20,
            key="login_matricule"
        )

        password_login = st.text_input(
            "Mot de passe",
            type="password",
            placeholder="••••••••",
            help="Votre mot de passe",
            max_chars=50,
            key="login_password"
        )

        # Afficher le statut des tentatives si nécessaire
        if st.session_state.login_attempts > 0:
            can_login, seconds = check_login_cooldown()
            if not can_login:
                st.warning(f"⏱️ Attendez {seconds} secondes avant de réessayer")

        # Bouton de connexion
        col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
        with col_btn2:
            if st.button("🚀 Se connecter", use_container_width=True, key="btn_login"):
                handle_login(matricule_login, password_login)

        # Informations supplémentaires
        with st.expander("ℹ️ Besoin d'aide ?"):
            st.markdown("""
            **Problèmes de connexion ?**
            - Vérifiez votre matricule et mot de passe
            - Contactez le support IT: support@sgci.ci
            - Tél: 2322
            """)

    # ========== TAB INSCRIPTION ==========
    with tab2:
        st.markdown("### ✍️ Créez votre compte")

        with st.form("registration_form"):
            matricule_reg = st.text_input(
                "Matricule *",
                placeholder="Votre matricule SGCI",
                help="Minimum 4 caractères",
                max_chars=20
            )

            col1, col2 = st.columns(2)
            with col1:
                nom_reg = st.text_input(
                    "Nom *",
                    placeholder="Votre nom",
                    max_chars=50
                )
            with col2:
                prenom_reg = st.text_input(
                    "Prénom *",
                    placeholder="Votre prénom",
                    max_chars=50
                )

            email_reg = st.text_input(
                "Email *",
                placeholder="prenom.nom@sgci.ci",
                help="Votre adresse email professionnelle",
                max_chars=100
            )

            password_reg = st.text_input(
                "Mot de passe *",
                type="password",
                placeholder="••••••••",
                help="Minimum 4 caractères",
                max_chars=50
            )

            confirm_password_reg = st.text_input(
                "Confirmer le mot de passe *",
                type="password",
                placeholder="••••••••",
                max_chars=50
            )

            st.markdown("*Tous les champs sont obligatoires*")

            # Bouton de soumission
            submitted = st.form_submit_button("📝 Créer mon compte", use_container_width=True)

            if submitted:
                handle_registration(
                    matricule_reg,
                    nom_reg,
                    prenom_reg,
                    email_reg,
                    password_reg,
                    confirm_password_reg
                )

    # Footer
    st.markdown("""
        <div class="footer">
            © 2025 Société Générale Côte d'Ivoire - Tous droits réservés<br>
            🔒 Connexion sécurisée | Version 1.0
        </div>
    """, unsafe_allow_html=True)

    # Empêcher l'affichage du reste de l'app
    st.stop()

else:
    # ========== PAGE D'ACCUEIL (APRÈS CONNEXION) ==========

    # Sidebar avec info utilisateur
    with st.sidebar:
        # Navigation

        if st.session_state.role == "admin":
            if st.button("⚙️ Administration", use_container_width=True):
                st.switch_page("pages/admin.py")

            if st.button("📄 Documents", use_container_width=True):
                st.switch_page("pages/documents.py")

        if st.session_state.role in ("juridique", "rh", "user"):

            if st.button("💬 Chat", use_container_width=True):
                st.switch_page("pages/chat.py")

            if st.button("📄 Documents", use_container_width=True):
                st.switch_page("pages/documents.py")

        st.markdown("---")

        # Bouton déconnexion
        if st.button("🔓 Logout", use_container_width=True, type="primary"):
            handle_logout()

    # Contenu principal - Page d'accueil
    st.title("🏠 Accueil - Chatbot SGCI")

    st.markdown(f"""
        <div class="welcome-message">
            <h2>Bienvenue {st.session_state.prenom} ! 👋</h2>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # Cards de navigation
    col1, col2 = st.columns(2)

    with col1:
        with st.container():
            st.markdown("### 💬 Chat Assistant")
            st.markdown("""
            Discutez avec l'assistant IA pour obtenir des réponses à vos questions 
            sur la banque, les produits et services.

            **Fonctionnalités:**
            - Questions/Réponses en temps réel
            - Historique des conversations
            - Export des échanges
            """)
            if st.button("Accéder au Chat →", key="nav_chat"):
                st.switch_page("pages/chat.py")

    with col2:
        with st.container():
            st.markdown("### 📄 Gestion Documents")
            st.markdown("""
            Chargez et gérez vos documents pour enrichir la base de 
            connaissances du chatbot.

            **Fonctionnalités:**
            - Upload de fichiers (PDF, DOCX, TXT)
            - Indexation automatique
            - Gestion des documents
            """)
            if st.button("Accéder aux Documents →", key="nav_docs"):
                st.switch_page("pages/documents.py")

    # Footer
    st.markdown("""
        <div class="footer">
            © 2025 Société Générale Côte d'Ivoire | Support: Direction Innovation
        </div>
    """, unsafe_allow_html=True)