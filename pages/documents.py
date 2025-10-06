import streamlit as st
import tempfile
from uuid import uuid4
from datetime import datetime
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from src.vectorstore import get_vector_store
from langchain_openai import OpenAIEmbeddings
from src import CONFIG
import pandas as pd

OPENAI_API_KEY = CONFIG["OPENAI_API_KEY"]
BASE_DIR = "./collections"

embeddings = OpenAIEmbeddings(api_key=OPENAI_API_KEY)

# --- Configuration de la page ---
st.set_page_config(
    page_title="Gestion des Documents",
    page_icon="📂",
    layout="wide"
)

# --- Vérification login ---
if "logged_in" not in st.session_state or not st.session_state.logged_in:
    st.error("🚫 Accès refusé. Veuillez vous connecter.")
    if st.button("🔑 Retour à la connexion", type="primary"):
        st.switch_page("app.py")
    st.stop()

# --- En-tête avec informations utilisateur ---
col1, col2 = st.columns([3, 1])
with col1:
    st.title("📂 Gestion des Documents")
with col2:
    st.markdown(f"""
    <div style='text-align: right; padding: 10px;'>
        <p style='margin: 0;'><strong>👤 {st.session_state.nom} {st.session_state.prenom}</strong></p>
        <p style='margin: 0; color: #666;'>{st.session_state.role.upper()}</p>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# Initialisation du vector store
vector_store = get_vector_store()


# === FONCTION DE TRAITEMENT DES FICHIERS ===
def process_file(uploaded_file):
    """Traite un fichier et retourne les documents splittés."""
    ext = uploaded_file.name.split(".")[-1].lower()
    docs = []

    try:
        if ext == "pdf":
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(uploaded_file.getbuffer())
                tmp_path = tmp_file.name

            loader = PyPDFLoader(tmp_path)
            pages = loader.load()

            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=520,
                chunk_overlap=20,
                length_function=len
            )
            docs = text_splitter.split_documents(pages)

        elif ext in ["xlsx", "xls", "csv"]:
            if ext == "csv":
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)

            text_content = df.to_csv(index=False)
            docs = [type("Doc", (), {"page_content": text_content, "metadata": {}})]
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=50
            )
            docs = text_splitter.split_documents(docs)

        return docs, None
    except Exception as e:
        return None, str(e)


# === SECTION UPLOAD (admin uniquement) ===
if st.session_state.role == "admin":
    with st.expander("📤 Chargement de nouveaux documents", expanded=False):
        st.info("💡 Formats acceptés : PDF, Excel (.xlsx, .xls), CSV")

        uploaded_files = st.file_uploader(
            "Sélectionnez un ou plusieurs fichiers",
            type=["pdf", "xlsx", "xls", "csv"],
            accept_multiple_files=True,
            help="Vous pouvez charger plusieurs fichiers à la fois"
        )

        if uploaded_files:
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("✅ Ajouter à la base", type="primary", use_container_width=True):
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    success_count = 0
                    error_count = 0

                    for idx, uploaded_file in enumerate(uploaded_files):
                        status_text.text(f"Traitement de {uploaded_file.name}...")

                        docs, error = process_file(uploaded_file)

                        if error:
                            st.error(f"❌ Erreur avec '{uploaded_file.name}': {error}")
                            error_count += 1
                        else:
                            # Ajout des métadonnées
                            doc_id = str(uuid4())
                            date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            uploader = f"{st.session_state.nom} {st.session_state.prenom}"

                            for d in docs:
                                d.metadata.update({
                                    "doc_id": doc_id,
                                    "filename": uploaded_file.name,
                                    "date_added": date_str,
                                    "uploaded_by_role": st.session_state.role,
                                    "uploader": uploader
                                })

                            vector_store.add_documents(
                                ids=[str(uuid4()) for _ in range(len(docs))],
                                documents=docs
                            )
                            success_count += 1

                        progress_bar.progress((idx + 1) / len(uploaded_files))

                    status_text.empty()
                    progress_bar.empty()

                    if success_count > 0:
                        st.success(f"✅ {success_count} document(s) ajouté(s) avec succès !")
                    if error_count > 0:
                        st.warning(f"⚠️ {error_count} document(s) en erreur.")

                    st.rerun()
else:
    st.info("ℹ️ Seuls les administrateurs peuvent charger de nouveaux documents.")

st.divider()

# === CONSULTATION ET GESTION DES DOCUMENTS ===
st.subheader("📑 Documents enregistrés")

try:
    results = vector_store.get(include=["metadatas"])
    metadatas = results["metadatas"]
    ids = results["ids"]

    if metadatas:
        # Construction des données uniques
        unique_docs = {}
        chunk_map = {}
        for i, meta in enumerate(metadatas):
            doc_id = meta.get("doc_id")
            if doc_id not in unique_docs:
                unique_docs[doc_id] = {
                    "Nom": meta.get("filename", "N/A"),
                    "Date": meta.get("date_added", "N/A"),
                    "Rôle": meta.get("uploaded_by_role", "N/A"),
                    "Username": meta.get("uploader", "N/A")
                }
            chunk_map.setdefault(doc_id, []).append(ids[i])

        # Statistiques
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📚 Total documents", len(unique_docs))
        with col2:
            total_chunks = len(ids)
            st.metric("🧩 Total fragments", total_chunks)
        with col3:
            avg_chunks = total_chunks / len(unique_docs) if unique_docs else 0
            st.metric("📊 Moy. fragments/doc", f"{avg_chunks:.1f}")

        st.divider()

        # Filtres
        col1, col2, col3 = st.columns([2, 2, 2])
        with col1:
            search_term = st.text_input("🔍 Rechercher par nom", "")
        with col2:
            filter_role = st.selectbox(
                "Filtrer par rôle",
                ["Tous"] + list(set([d["Rôle"] for d in unique_docs.values()]))
            )
        with col3:
            sort_by = st.selectbox(
                "Trier par",
                ["Date (récent)", "Date (ancien)", "Nom (A-Z)", "Nom (Z-A)"]
            )

        # Application des filtres
        filtered_docs = unique_docs.copy()

        if search_term:
            filtered_docs = {
                k: v for k, v in filtered_docs.items()
                if search_term.lower() in v["Nom"].lower()
            }

        if filter_role != "Tous":
            filtered_docs = {
                k: v for k, v in filtered_docs.items()
                if v["Rôle"] == filter_role
            }

        # Tri
        if sort_by == "Date (récent)":
            filtered_docs = dict(sorted(filtered_docs.items(), key=lambda x: x[1]["Date"], reverse=True))
        elif sort_by == "Date (ancien)":
            filtered_docs = dict(sorted(filtered_docs.items(), key=lambda x: x[1]["Date"]))
        elif sort_by == "Nom (A-Z)":
            filtered_docs = dict(sorted(filtered_docs.items(), key=lambda x: x[1]["Nom"]))
        else:
            filtered_docs = dict(sorted(filtered_docs.items(), key=lambda x: x[1]["Nom"], reverse=True))

        st.caption(f"Affichage de {len(filtered_docs)} document(s)")

        # Affichage des documents
        if filtered_docs:
            # En-tête
            if st.session_state.role == "admin":
                cols = st.columns([0.5, 3, 2, 1.5, 1.5])
                cols[0].markdown("**☑️**")
            else:
                cols = st.columns([3, 2, 1.5, 1.5])

            offset = 1 if st.session_state.role == "admin" else 0
            cols[offset].markdown("**📄 Nom du fichier**")
            cols[offset + 1].markdown("**📅 Date d'ajout**")
            cols[offset + 2].markdown("**👤 Uploadé par**")
            cols[offset + 3].markdown("**🎭 Rôle**")

            st.divider()

            # Liste des documents
            selected = []
            for doc_id, infos in filtered_docs.items():
                if st.session_state.role == "admin":
                    cols = st.columns([0.5, 3, 2, 1.5, 1.5])
                    with cols[0]:
                        checked = st.checkbox("", key=doc_id, label_visibility="collapsed")
                        if checked:
                            selected.append(doc_id)
                    col_offset = 1
                else:
                    cols = st.columns([3, 2, 1.5, 1.5])
                    col_offset = 0

                with cols[col_offset]:
                    st.markdown(f"📄 {infos['Nom']}")
                with cols[col_offset + 1]:
                    st.markdown(f"{infos['Date']}")
                with cols[col_offset + 2]:
                    st.markdown(f"{infos['Username']}")
                with cols[col_offset + 3]:
                    role_emoji = "👑" if infos['Rôle'] == "admin" else "👤"
                    st.markdown(f"{role_emoji} {infos['Rôle']}")

            # Suppression (admin uniquement)
            if st.session_state.role == "admin" and selected:
                st.divider()
                col1, col2, col3 = st.columns([1, 1, 3])
                with col1:
                    if st.button(f"🗑️ Supprimer ({len(selected)})", type="primary", use_container_width=True):
                        for doc_id in selected:
                            vector_store.delete(ids=chunk_map[doc_id])
                        st.success(f"✅ {len(selected)} document(s) supprimé(s) avec succès !")
                        st.rerun()
                with col2:
                    if st.button("❌ Annuler", use_container_width=True):
                        st.rerun()
        else:
            st.info("Aucun document ne correspond aux filtres sélectionnés.")
    else:
        st.info("📭 Aucun document n'a encore été chargé dans la base.")
        if st.session_state.role == "admin":
            st.caption("👆 Utilisez la section ci-dessus pour charger vos premiers documents.")

except Exception as e:
    st.error(f"⚠️ Erreur lors de la lecture des documents : {e}")
    st.caption("Veuillez vérifier la connexion à la base de données.")
