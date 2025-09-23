import streamlit as st
import tempfile
from uuid import uuid4
from datetime import datetime
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from src.vectorstore import get_vector_store
from langchain_openai import OpenAIEmbeddings
from src import CONFIG

OPENAI_API_KEY = CONFIG["OPENAI_API_KEY"]
BASE_DIR = "./collections"

embeddings = OpenAIEmbeddings(api_key=OPENAI_API_KEY)

# --- Vérification login ---
if "logged_in" not in st.session_state or not st.session_state.logged_in:
    st.error("🚫 Accès refusé. Veuillez vous connecter.")
    if st.button("🔑 Retour à la connexion"):
        st.switch_page("app.py")
    st.stop()

st.set_page_config(page_title="Gestion des Documents", page_icon="📂")
st.title("📂 Gestion des Documents")

vector_store = get_vector_store()

# === Upload ===
uploaded_file = st.file_uploader("Charger un PDF", type="pdf")
if uploaded_file:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(uploaded_file.getbuffer())
        tmp_path = tmp_file.name

    # Charger et splitter
    loader = PyPDFLoader(tmp_path)
    pages = loader.load()

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=520, chunk_overlap=20,length_function=len)
    docs = text_splitter.split_documents(pages)

    # Ajouter des métadonnées
    doc_id = str(uuid4())
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    role_uploader = st.session_state.role  # rôle de l’utilisateur qui upload
    uploader = f"{st.session_state.nom} {st.session_state.prenom}"

    for d in docs:
        d.metadata.update({
            "doc_id": doc_id,
            "filename": uploaded_file.name,
            "date_added": date_str,
            "uploaded_by_role": role_uploader,
            "uploader": uploader
        })

    vector_store.add_documents(
        ids=[str(uuid4()) for _ in range(len(docs))],
        documents=docs
    )

    st.success(f"✅ Document '{uploaded_file.name}' ajouté à la base par {uploader}.")

# documents
try:
    results = vector_store.get(include=["metadatas"])
    metadatas = results["metadatas"]
    ids = results["ids"]

    if metadatas:
        # Filtrer selon rôle
        if st.session_state.role != "admin":
            metadatas_filtered = [
                (i, m) for i, m in enumerate(metadatas)
                if m.get("uploaded_by_role") == st.session_state.role
            ]
        else:
            metadatas_filtered = list(enumerate(metadatas))

        # Regrouper par doc_id
        unique_docs = {}
        chunk_map = {}
        for i, meta in metadatas_filtered:
            doc_id = meta.get("doc_id")
            if doc_id not in unique_docs:
                unique_docs[doc_id] = {
                    "Nom": meta.get("filename", "N/A"),
                    "Date": meta.get("date_added", "N/A"),
                    "Rôle": meta.get("uploaded_by_role", "N/A"),
                    "Username": meta.get("uploader", "N/A")
                }
            chunk_map.setdefault(doc_id, []).append(ids[i])

        st.subheader("📑 Documents enregistrés")
        selected = []
        for doc_id, infos in unique_docs.items():
            col1, col2, col3, col4, col5 = st.columns([0.05, 0.4, 0.3, 0.25, 0.2])
            with col1:
                checked = st.checkbox("", key=doc_id)
                if checked:
                    selected.append(doc_id)
            with col2:
                st.markdown(f"**{infos['Nom']}**")
            with col3:
                st.markdown(f"📅 {infos['Date']}")
            with col4:
                st.markdown(f"**{infos['Rôle']}**")
            with col5:
                st.markdown(f"👤 {infos['Username']}")


        if selected and st.button("🗑️ Supprimer la sélection"):
            for doc_id in selected:
                vector_store.delete(ids=chunk_map[doc_id])
            st.success(f"✅ {len(selected)} document(s) supprimé(s).")
            st.rerun()
    else:
        st.info("Aucun document n’a encore été chargé.")
except Exception as e:
    st.warning(f"⚠️ Impossible de lire les documents enregistrés : {e}")
