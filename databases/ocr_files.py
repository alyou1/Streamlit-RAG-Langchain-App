import streamlit as st
import tempfile
import os
import shutil
from uuid import uuid4
from datetime import datetime
from pathlib import Path
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document

from src.vectorstore import get_vector_store
from langchain_openai import OpenAIEmbeddings
from src import CONFIG
import pandas as pd
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import io

# ============================================
# CONFIGURATION
# ============================================

OPENAI_API_KEY = CONFIG["OPENAI_API_KEY"]
BASE_DIR = "./collections"

embeddings = OpenAIEmbeddings(api_key=OPENAI_API_KEY)

# Configuration de la page
st.set_page_config(
    page_title="Traitement_OCR",
    page_icon="📂",
    layout="wide"
)

# Initialisation du vector store
vector_store = get_vector_store()


def extract_text_from_scanned_pdf(pdf_path):
    """
    Extrait le texte d'un PDF scanné en utilisant OCR avec Tesseract.
    Utilise pdf2image au lieu de PyMuPDF pour éviter les conflits.
    """
    try:
        # Convertir le PDF en images
        images = convert_from_path(pdf_path, dpi=300)

        extracted_text = []

        for page_num, image in enumerate(images):
            custom_config = r'--oem 3 --psm 6 -l fra+eng'
            text = pytesseract.image_to_string(image, config=custom_config)

            if text.strip():
                extracted_text.append(text)

        full_text = "\n\n".join(extracted_text)
        return full_text.strip() if full_text.strip() else None

    except Exception as e:
        st.error(f"❌ Erreur lors de l'extraction OCR: {str(e)}")
        return None


def process_file(uploaded_file):
    """
    Traite un fichier et retourne les documents splittés.
    Gère automatiquement les PDFs scannés avec OCR.
    """
    ext = uploaded_file.name.split(".")[-1].lower()
    docs = []

    try:
        if ext == "pdf":
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(uploaded_file.getbuffer())
                tmp_path = tmp_file.name

            # Tentative de chargement classique
            loader = PyPDFLoader(tmp_path)
            pages = loader.load()

            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=520,
                chunk_overlap=20,
                length_function=len
            )
            docs = text_splitter.split_documents(pages)

            # Vérifier si c'est un PDF scanné
            total_chars = sum(len(doc.page_content.strip()) for doc in docs)
            avg_chars_per_page = total_chars / len(pages) if len(pages) > 0 else 0

            if len(docs) == 0 or avg_chars_per_page < 100:
                st.info("📄 PDF scanné détecté. Application de l'OCR en cours...")

                ocr_text = extract_text_from_scanned_pdf(tmp_path)

                if ocr_text:
                    docs = [type("Doc", (), {
                        "page_content": ocr_text,
                        "metadata": {}
                    })]
                    docs = text_splitter.split_documents(docs)
                    st.success(f"✅ OCR terminé: {len(docs)} chunks créés")
                else:
                    st.warning("⚠️ Impossible d'extraire le texte du PDF scanné")
                    docs = []

            os.remove(tmp_path)

        elif ext == "txt":
            content = uploaded_file.read().decode("utf-8")
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=520,
                chunk_overlap=20,
                length_function=len
            )
            docs = [type("Doc", (), {"page_content": content, "metadata": {}})]
            docs = text_splitter.split_documents(docs)

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


# ============================================
# INTERFACE STREAMLIT
# ============================================

# Section pour admin/super_user
if st.session_state.get("role") in ("admin", "super_user"):
    with st.expander("📁 Chargement de nouveaux documents", expanded=False):
        st.info("ℹ️ Formats acceptés : PDF, Excel (.xlsx, .xls), CSV, Texte (.txt)")
        st.info("📄 Les PDFs scannés sont automatiquement traités par OCR (Tesseract)")

        admin_uploaded_files = st.file_uploader(
            "Sélectionnez un ou plusieurs fichiers",
            type=["pdf", "xlsx", "xls", "csv", "txt"],
            accept_multiple_files=True,
            help="Vous pouvez charger plusieurs fichiers à la fois",
            key="admin_uploader"
        )

        if admin_uploaded_files:
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("➕ Ajouter à la base", type="primary", use_container_width=True):
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    success_count = 0
                    error_count = 0

                    for idx, uploaded_file in enumerate(admin_uploaded_files):
                        status_text.text(f"Traitement de {uploaded_file.name}...")

                        docs, error = process_file(uploaded_file)

                        if error:
                            st.error(f"❌ Erreur avec '{uploaded_file.name}': {error}")
                            error_count += 1
                        else:
                            if docs and len(docs) > 0:
                                # Ajout des métadonnées
                                doc_id = str(uuid4())
                                date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                uploader = f"{st.session_state.get('nom', 'N/A')} {st.session_state.get('prenom', 'N/A')}"

                                for d in docs:
                                    d.metadata.update({
                                        "doc_id": doc_id,
                                        "filename": uploaded_file.name,
                                        "date_added": date_str,
                                        "uploaded_by_role": st.session_state.get("role", "unknown"),
                                        "uploader": uploader
                                    })

                                # Chargement dans la base vectorielle
                                if len(docs) <= 512:
                                    vector_store.add_documents(
                                        ids=[str(uuid4()) for _ in range(len(docs))],
                                        documents=docs
                                    )
                                    success_count += 1
                                else:
                                    # Traitement par batch pour les gros documents
                                    batch_size = 512
                                    for i in range(0, len(docs), batch_size):
                                        batch_docs = docs[i:i + batch_size]
                                        batch_ids = [str(uuid4()) for _ in range(len(batch_docs))]

                                        vector_store.add_documents(
                                            ids=batch_ids,
                                            documents=batch_docs
                                        )
                                    success_count += 1
                            else:
                                st.warning(f"⚠️ Aucun contenu extractible de '{uploaded_file.name}'")
                                error_count += 1

                        # Mise à jour de la progression
                        progress_bar.progress((idx + 1) / len(admin_uploaded_files))

                    # Fin du traitement
                    status_text.empty()
                    progress_bar.empty()

                    if success_count > 0:
                        st.success(f"✅ {success_count} document(s) ajouté(s) avec succès !")
                    if error_count > 0:
                        st.warning(f"⚠️ {error_count} document(s) en erreur.")

                    st.rerun()
else:
    st.info("ℹ️ Seuls les administrateurs et les éditeurs peuvent charger de nouveaux documents.")

st.divider()

# ============================================
# SECTION APERÇU ET TEST
# ============================================

st.subheader("🔍 Tester l'extraction OCR")

uploaded_files = st.file_uploader(
    "Sélectionnez un ou plusieurs fichiers pour tester",
    type=["pdf", "xlsx", "xls", "csv", "txt"],
    accept_multiple_files=True,
    help="Vous pouvez charger plusieurs fichiers à la fois. Les PDFs avec images seront traités par OCR.",
    key="test_uploader"
)

if uploaded_files:
    # Aperçu des documents
    st.subheader("📄 Aperçu des documents")

    # Sélection du fichier à prévisualiser
    if len(uploaded_files) > 1:
        preview_file = st.selectbox(
            "Choisir un fichier à prévisualiser",
            uploaded_files,
            format_func=lambda x: x.name
        )
    else:
        preview_file = uploaded_files[0]

    # Afficher l'aperçu
    with st.expander(f"👁️ Aperçu de '{preview_file.name}'", expanded=True):
        docs, error = process_file(preview_file)

        if error:
            st.error(f"Erreur lors du chargement: {error}")
        else:
            # Reconstituer le contenu complet
            full_content = "\n\n".join([doc.page_content for doc in docs])

            # Afficher les informations du document
            col_info1, col_info2, col_info3 = st.columns(3)
            with col_info1:
                st.metric("Nombre de chunks", len(docs))
            with col_info2:
                st.metric("Nombre de caractères", len(full_content))
            with col_info3:
                if docs and docs[0].metadata.get("ocr_processed"):
                    st.metric("Type", "OCR 🔍")
                else:
                    st.metric("Type", "Texte natif 📝")

            # Afficher le contenu complet
            st.text_area(
                "Contenu complet du document",
                value=full_content,
                height=400,
                label_visibility="visible"
            )

    st.divider()

    # Bouton pour ajouter à la base
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("✅ Ajouter à la base", type="primary", use_container_width=True, key="add_test_files"):
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
                    if docs and len(docs) > 0:
                        # Ajout des métadonnées
                        doc_id = str(uuid4())
                        date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                        for d in docs:
                            d.metadata.update({
                                "doc_id": doc_id,
                                "filename": uploaded_file.name,
                                "date_added": date_str
                            })

                        vector_store.add_documents(
                            ids=[str(uuid4()) for _ in range(len(docs))],
                            documents=docs
                        )
                        success_count += 1
                    else:
                        st.warning(f"⚠️ Aucun contenu extractible de '{uploaded_file.name}'")
                        error_count += 1

                progress_bar.progress((idx + 1) / len(uploaded_files))

            status_text.empty()
            progress_bar.empty()

            if success_count > 0:
                st.success(f"✅ {success_count} document(s) ajouté(s) avec succès !")
            if error_count > 0:
                st.warning(f"⚠️ {error_count} document(s) en erreur.")

            st.rerun()
