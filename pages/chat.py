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
from chat_db import init_chat_table, load_conversations, save_message  # ajout DB

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

# --- Sidebar : gestion des conversations ---
with st.sidebar:
    st.subheader("💬 Gestion des conversations")

    conv_names = list(st.session_state.conversations.keys())

    # Sélection conversation
    selected_conv = st.selectbox(
        "📂 Sélectionner une conversation",
        conv_names,
        index=conv_names.index(st.session_state.active_conv),
        key="conv_selectbox"
    )
    st.session_state.active_conv = selected_conv

    # Actions (nouvelle / supprimer)
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("➕ Nouvelle", use_container_width=True):
            new_name = f"Conversation {len(conv_names) + 1}"
            st.session_state.conversations[new_name] = []
            st.session_state.active_conv = new_name
            st.rerun()

    with col2:
        if st.button("🗑️ Supprimer", use_container_width=True):
            conv_to_delete = st.session_state.active_conv

            # Supprimer en mémoire
            st.session_state.conversations.pop(conv_to_delete, None)

            # Supprimer aussi en DB
            from chat_db import delete_conversation
            delete_conversation(matricule, conv_to_delete)

            # Rester sur une autre conv si dispo
            if st.session_state.conversations:
                st.session_state.active_conv = list(st.session_state.conversations.keys())[0]
            else:
                st.session_state.conversations = {"Conversation 1": []}
                st.session_state.active_conv = "Conversation 1"

            st.success(f"✅ {conv_to_delete} supprimée.")
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
            "history": lambda _: history,  # injecte l’historique texte
        }
        | prompt
        | llm
        | StrOutputParser()
    )

# --- Affichage de l’historique ---
for msg in st.session_state.conversations[st.session_state.active_conv]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- Input utilisateur ---
if user_input := st.chat_input("💬 Pose ta question ici..."):
    # Ajout + sauvegarde du message utilisateur
    st.session_state.conversations[st.session_state.active_conv].append(
        {"role": "user", "content": user_input}
    )
    save_message(matricule, st.session_state.active_conv, "user", user_input)

    with st.chat_message("user"):
        st.markdown(user_input)

    # Construire historique (dernier 5 échanges par ex.)
    history = build_history(st.session_state.conversations[st.session_state.active_conv], limit=10)

    # Génération réponse avec mémoire
    chain_with_memory = build_chain(prompt, retriever, llm, history)

    response = chain_with_memory.invoke(user_input)

    with st.spinner("Génération de la réponse..."):
        with st.chat_message("assistant"):
            stream_text = st.write_stream(chat_stream(response))

    # Ajout + sauvegarde du message assistant
    st.session_state.conversations[st.session_state.active_conv].append(
        {"role": "assistant", "content": response}
    )
    save_message(matricule, st.session_state.active_conv, "assistant", response)
