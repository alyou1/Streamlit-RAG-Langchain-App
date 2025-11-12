import streamlit as st
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from prompts.prompt_rh import prompt_rh
from prompts.prompt_juridique import prompt_juridique
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from src.vectorstore import get_vector_store
from src import CONFIG
from src.utils import format_docs, chat_stream
from chat_db import init_chat_table, load_conversations, save_message, rename_conversation, get_feedback, save_feedback
import time

OPENAI_API_KEY = CONFIG["OPENAI_API_KEY"]
BASE_DIR = "./collections"

# --- Vérification login ---
if "logged_in" not in st.session_state or not st.session_state.logged_in:
    st.error("🚫 Accès refusé. Veuillez vous connecter.")
    if st.button("🔑 Retour à la connexion"):
        st.switch_page("app.py")
    st.stop()

# --- Vérification rôle ---
if st.session_state.role not in ("juridique", "rh"):
    st.error("🚫 Accès refusé. Seuls Les utilisateurs peuvent avoir accès au chat.")
    st.stop()

# --- Configuration de la page ---
st.set_page_config(
    page_title="Chatbot",
    page_icon="💬",
    layout="centered"
)

# --- CSS personnalisé pour l'affichage des conversations ---
st.markdown("""
<style>
    .conversation-item {
        padding: 12px 16px;
        margin: 4px 0;
        border-radius: 8px;
        cursor: pointer;
        transition: background-color 0.2s;
        border: 1px solid transparent;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .conversation-item:hover {
        background-color: rgba(151, 166, 195, 0.15);
    }
    .conversation-item.active {
        background-color: rgba(151, 166, 195, 0.25);
        border: 1px solid rgba(151, 166, 195, 0.4);
    }
    .conversation-name {
        font-size: 14px;
        color: inherit;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        flex-grow: 1;
    }
    .conversation-actions {
        display: flex;
        gap: 8px;
        margin-left: 8px;
    }
    .new-conv-btn {
        width: 100%;
        margin-bottom: 16px;
    }
</style>
""", unsafe_allow_html=True)

# --- Initialisation DB pour conversations ---
init_chat_table()
matricule = st.session_state["matricule"]

# Charger conversations depuis DB
if "conversations" not in st.session_state:
    st.session_state.conversations = load_conversations(matricule)
    if not st.session_state.conversations:
        st.session_state.conversations = {"Conversation 1": []}

if "active_conv" not in st.session_state:
    st.session_state.active_conv = list(st.session_state.conversations.keys())[0]

# Initialiser les feedbacks en session
if "feedbacks" not in st.session_state:
    st.session_state.feedbacks = {}

# Initialiser l'état pour la recherche
if "search_query" not in st.session_state:
    st.session_state.search_query = ""

# Initialiser l'état pour le renommage
if "rename_mode" not in st.session_state:
    st.session_state.rename_mode = {}

st.write(f"Bienvenue {st.session_state.nom} {st.session_state.prenom} 👋")

# --- Header avec bouton déconnexion ---
col1, col2 = st.columns([8, 1])
with col1:
    st.title("💬 Interrogez vos documents")
with col2:
    if st.button("🔓 "):
        st.session_state.clear()
        st.switch_page("app.py")


# --- Fonction pour générer un nom de conversation ---
def generate_conversation_name(user_message):
    """
    Génère un nom de conversation basé sur les premiers mots du message.
    Limite à 50 caractères maximum.
    """
    name = user_message.strip()

    if len(name) > 50:
        name = name[:47] + "..."

    if len(name) < 3:
        name = "Nouvelle conversation"

    return name


# --- Sidebar : gestion des conversations ---
with st.sidebar:
    st.subheader("💬 Conversations")

    # Bouton nouvelle conversation
    if st.button("➕ Nouvelle conversation", use_container_width=True, key="new_conv_btn"):
        new_name = f"Conversation {len(st.session_state.conversations) + 1}"
        st.session_state.conversations[new_name] = []
        st.session_state.active_conv = new_name
        st.rerun()

    st.markdown("---")

    # Barre de recherche avec mise à jour en temps réel
    search_query = st.text_input(
        "🔍 Rechercher une conversation",
        value=st.session_state.search_query,
        placeholder="Tapez pour filtrer...",
        key="search_input",
        on_change=lambda: None  # Force le rerun à chaque changement
    )

    # Détection du changement pour rerun automatique
    if search_query != st.session_state.search_query:
        st.session_state.search_query = search_query
        st.rerun()

    st.session_state.search_query = search_query

    st.markdown("---")

    # Liste des conversations avec filtrage
    conv_names = list(st.session_state.conversations.keys())

    # Filtrer les conversations selon la recherche
    if search_query:
        filtered_convs = [name for name in conv_names if search_query.lower() in name.lower()]
    else:
        filtered_convs = conv_names

    # Afficher le nombre de résultats
    if search_query:
        st.caption(f"📊 {len(filtered_convs)} conversation(s) trouvée(s)")

    if not filtered_convs:
        st.info("Aucune conversation ne correspond à votre recherche")
    else:
        for conv_name in filtered_convs:
            # Vérifier si on est en mode renommage pour cette conversation
            is_renaming = st.session_state.rename_mode.get(conv_name, False)

            if is_renaming:
                # Mode renommage : afficher un champ texte
                col1, col2, col3 = st.columns([5, 0.5, 0.5])

                with col1:
                    new_name = st.text_input(
                        "Nouveau nom",
                        value=conv_name,
                        key=f"rename_input_{conv_name}",
                        label_visibility="collapsed"
                    )

                with col2:
                    # Bouton valider
                    if st.button("✅", key=f"save_rename_{conv_name}", help="Valider"):
                        if new_name and new_name != conv_name:
                            # Vérifier que le nom n'existe pas déjà
                            if new_name not in st.session_state.conversations:
                                # Renommer en mémoire
                                st.session_state.conversations[new_name] = st.session_state.conversations.pop(conv_name)

                                # Renommer en DB
                                rename_conversation(matricule, conv_name, new_name)

                                # Mettre à jour la conversation active si nécessaire
                                if st.session_state.active_conv == conv_name:
                                    st.session_state.active_conv = new_name

                                st.session_state.rename_mode[conv_name] = False
                                st.toast(f"✅ Conversation renommée : {new_name}", icon="✅")
                                st.rerun()
                            else:
                                st.error("Ce nom existe déjà")

                with col3:
                    # Bouton annuler
                    if st.button("❌", key=f"cancel_rename_{conv_name}", help="Annuler"):
                        st.session_state.rename_mode[conv_name] = False
                        st.rerun()

            else:
                # Mode normal : afficher le bouton de conversation
                col1, col2, col3 = st.columns([5, 0.5, 0.5])

                with col1:
                    # Bouton pour sélectionner la conversation
                    is_active = conv_name == st.session_state.active_conv
                    button_type = "primary" if is_active else "secondary"

                    if st.button(
                            f"💬 {conv_name}",
                            key=f"conv_{conv_name}",
                            use_container_width=True,
                            type=button_type
                    ):
                        st.session_state.active_conv = conv_name
                        st.rerun()

                with col2:
                    # Bouton renommer
                    if st.button("✏️", key=f"rename_{conv_name}", help="Renommer"):
                        st.session_state.rename_mode[conv_name] = True
                        st.rerun()

                with col3:
                    # Bouton supprimer
                    if st.button("🗑️", key=f"del_{conv_name}", help="Supprimer"):
                        # Supprimer en mémoire
                        st.session_state.conversations.pop(conv_name, None)

                        # Supprimer aussi en DB
                        from chat_db import delete_conversation

                        delete_conversation(matricule, conv_name)

                        # Rester sur une autre conv si dispo
                        if st.session_state.conversations:
                            st.session_state.active_conv = list(st.session_state.conversations.keys())[0]
                        else:
                            st.session_state.conversations = {"Conversation 1": []}
                            st.session_state.active_conv = "Conversation 1"

                        st.rerun()

# --- Préparation du modèle et du retriever ---
vector_store = get_vector_store()
llm = ChatOpenAI(model="gpt-4o-mini", api_key=OPENAI_API_KEY, temperature=0.7)


# --- Construire l'historique pour la mémoire ---
def build_history(conversation_msgs, limit=5):
    """
    Construit l'historique textuel à injecter dans le prompt.
    On limite aux X derniers messages pour ne pas surcharger.
    """
    history = ""
    for msg in conversation_msgs[-limit:]:
        prefix = "Utilisateur" if msg["role"] == "user" else "Assistant"
        history += f"{prefix} : {msg['content']}\n"
    return history


# --- Vérification rôle utilisateur ---
role = st.session_state.role

if role == "juridique":
    prompt = prompt_juridique
elif role == "rh":
    prompt = prompt_rh
else:
    st.error("🚫 Rôle non reconnu pour le chatbot.")
    st.stop()

retriever = vector_store.as_retriever(
    search_type="similarity_score_threshold",
    search_kwargs={"score_threshold": 0.5, "k": 5}
)


# --- Fonction pour construire la chaîne avec mémoire ---
def build_chain(prompt, retriever, llm, history):
    return (
            {
                "context": retriever | format_docs,
                "question": RunnablePassthrough(),
                "history": lambda _: history,
            }
            | prompt
            | llm
            | StrOutputParser()
    )


# --- Affichage de l'historique ---
current_conv_messages = st.session_state.conversations[st.session_state.active_conv]
for idx, msg in enumerate(current_conv_messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        # Afficher le feedback seulement pour les réponses de l'assistant
        if msg["role"] == "assistant":
            # Clé unique pour ce message
            feedback_key = f"{st.session_state.active_conv}_{idx}"

            # Récupérer le feedback existant
            if feedback_key not in st.session_state.feedbacks:
                st.session_state.feedbacks[feedback_key] = get_feedback(
                    matricule,
                    st.session_state.active_conv,
                    idx
                )

            # Afficher le widget de feedback
            feedback = st.feedback(
                "thumbs",
                key=f"feedback_{feedback_key}",
                disabled=False
            )

            # Sauvegarder si feedback modifié
            if feedback is not None:
                feedback_type = "positive" if feedback == 1 else "negative"
                if st.session_state.feedbacks.get(feedback_key) != feedback_type:
                    save_feedback(matricule, st.session_state.active_conv, idx, feedback_type)
                    st.session_state.feedbacks[feedback_key] = feedback_type
                    st.toast(f"✅ Feedback enregistré : {'👍' if feedback == 1 else '👎'}", icon="✅")

# --- Input utilisateur ---
if user_input := st.chat_input("💬 Pose ta question ici..."):
    current_conv_name = st.session_state.active_conv

    # Si c'est le premier message d'une conversation générique, renommer
    if (current_conv_name.startswith("Conversation ") and
            len(st.session_state.conversations[current_conv_name]) == 0):

        # Générer nouveau nom basé sur le message
        new_name = generate_conversation_name(user_input)

        # Vérifier unicité du nom
        original_name = new_name
        counter = 1
        while new_name in st.session_state.conversations:
            new_name = f"{original_name} ({counter})"
            counter += 1

        # Renommer dans la session
        st.session_state.conversations[new_name] = st.session_state.conversations.pop(current_conv_name)

        # Renommer en DB
        rename_conversation(matricule, current_conv_name, new_name)

        # Mettre à jour la conversation active
        st.session_state.active_conv = new_name
        current_conv_name = new_name

    # Ajout + sauvegarde du message utilisateur
    st.session_state.conversations[current_conv_name].append(
        {"role": "user", "content": user_input}
    )
    save_message(matricule, current_conv_name, "user", user_input)

    with st.chat_message("user"):
        st.markdown(user_input)

    # Construire historique
    history = build_history(st.session_state.conversations[current_conv_name], limit=10)

    # Génération réponse avec mémoire
    chain_with_memory = build_chain(prompt, retriever, llm, history)

    # ⏱️ Capturer le temps de début de génération
    start_time = time.time()

    response = chain_with_memory.invoke(user_input)

    # ⏱️ Capturer le temps de fin de génération
    end_time = time.time()
    response_time = end_time - start_time

    with st.spinner("Génération de la réponse..."):
        with st.chat_message("assistant"):
            stream_text = st.write_stream(chat_stream(response))

    # Ajout + sauvegarde du message assistant avec temps de réponse
    st.session_state.conversations[current_conv_name].append(
        {"role": "assistant", "content": response}
    )
    save_message(matricule, current_conv_name, "assistant", response, response_time)

    # Rerun pour afficher le feedback sur le nouveau message
    st.rerun()