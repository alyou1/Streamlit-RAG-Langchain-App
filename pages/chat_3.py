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
from chat_db import init_chat_table, load_conversations, save_message, rename_conversation

OPENAI_API_KEY = CONFIG["OPENAI_API_KEY"]
BASE_DIR = "./collections"

# --- Vérification login ---
if "logged_in" not in st.session_state or not st.session_state.logged_in:
    st.error("🚫 Accès refusé. Veuillez vous connecter.")
    if st.button("🔑 Retour à la connexion"):
        st.switch_page("app.py")
    st.stop()

# --- Vérification rôle ---
if st.session_state.role == "admin":
    st.error("🚫 Accès refusé. Les admins ne peuvent pas accéder au chat.")
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

    # Liste des conversations
    conv_names = list(st.session_state.conversations.keys())

    for conv_name in conv_names:
        col1, col2 = st.columns([5, 1])

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
llm = ChatOpenAI(model="gpt-4.1-mini", api_key=OPENAI_API_KEY, temperature=0.7)


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


# --- Affichage de l'en-tête de la conversation active ---
st.markdown(f"### 📝 {st.session_state.active_conv}")
st.markdown("---")

# --- Affichage de l'historique ---
for msg in st.session_state.conversations[st.session_state.active_conv]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

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

    response = chain_with_memory.invoke(user_input)

    with st.spinner("Génération de la réponse..."):
        with st.chat_message("assistant"):
            stream_text = st.write_stream(chat_stream(response))

    # Ajout + sauvegarde du message assistant
    st.session_state.conversations[current_conv_name].append(
        {"role": "assistant", "content": response}
    )
    save_message(matricule, current_conv_name, "assistant", response)
