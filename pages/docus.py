def extract_text_from_scanned_pdf(pdf_path):
    """
    Extrait le texte d'un PDF scanné en utilisant OCR avec Tesseract.
    
    Args:
        pdf_path: Chemin vers le fichier PDF scanné
        
    Returns:
        str: Texte extrait de toutes les pages, ou None en cas d'erreur
    """
    try:
        # Ouvrir le PDF avec PyMuPDF
        pdf_document = fitz.open(pdf_path)
        extracted_text = []
        
        # Parcourir toutes les pages
        for page_num in range(len(pdf_document)):
            page = pdf_document[page_num]
            
            # Extraire les images de la page
            image_list = page.get_images(full=True)
            
            if image_list:
                # Pour chaque image trouvée dans la page
                for img_index, img in enumerate(image_list):
                    xref = img[0]
                    base_image = pdf_document.extract_image(xref)
                    image_bytes = base_image["image"]
                    
                    # Convertir en image PIL
                    image = Image.open(io.BytesIO(image_bytes))
                    
                    # Appliquer l'OCR avec Tesseract
                    # Configuration: OEM 3 (meilleur moteur), PSM 6 (bloc de texte uniforme)
                    custom_config = r'--oem 3 --psm 6 -l fra+eng'
                    text = pytesseract.image_to_string(image, config=custom_config)
                    
                    if text.strip():
                        extracted_text.append(text)
            else:
                # Si pas d'images extraites, rendre la page entière en image
                # Matrix(2, 2) = zoom x2 pour meilleure qualité OCR
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                
                custom_config = r'--oem 3 --psm 6 -l fra+eng'
                text = pytesseract.image_to_string(img, config=custom_config)
                
                if text.strip():
                    extracted_text.append(text)
        
        pdf_document.close()
        
        # Combiner tout le texte extrait
        full_text = "\n\n".join(extracted_text)
        return full_text.strip() if full_text.strip() else None
        
    except Exception as e:
        st.error(f"❌ Erreur lors de l'extraction OCR: {str(e)}")
        return None

def process_file(uploaded_file):
    """
    Traite un fichier et retourne les documents splittés.
    Gère automatiquement les PDFs scannés avec OCR.
    
    Args:
        uploaded_file: Fichier uploadé via Streamlit
        
    Returns:
        tuple: (docs, error) - Liste de documents ou None, message d'erreur ou None
    """
    ext = uploaded_file.name.split(".")[-1].lower()
    docs = []
    
    try:
        if ext == "pdf":
            # Créer un fichier temporaire pour le PDF
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
            
            # Vérifier si c'est un PDF scanné (peu ou pas de texte)
            total_chars = sum(len(doc.page_content.strip()) for doc in docs)
            avg_chars_per_page = total_chars / len(pages) if len(pages) > 0 else 0
            
            # Si moins de 100 caractères par page en moyenne, c'est probablement scanné
            if len(docs) == 0 or avg_chars_per_page < 100:
                st.info("📄 PDF scanné détecté. Application de l'OCR en cours...")
                
                # Extraction du texte avec OCR
                ocr_text = extract_text_from_scanned_pdf(tmp_path)
                
                if ocr_text:
                    # Créer un document avec le texte OCR
                    docs = [type("Doc", (), {
                        "page_content": ocr_text,
                        "metadata": {}
                    })]
                    docs = text_splitter.split_documents(docs)
                    st.success(f"✅ OCR terminé: {len(docs)} chunks créés")
                else:
                    st.warning("⚠️ Impossible d'extraire le texte du PDF scanné")
                    docs = []
            
            # Nettoyage du fichier temporaire
            os.remove(tmp_path)
        
        elif ext == "txt":
            # Traitement des fichiers texte
            content = uploaded_file.read().decode("utf-8")
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=520,
                chunk_overlap=20,
                length_function=len
            )
            docs = [type("Doc", (), {"page_content": content, "metadata": {}})]
            docs = text_splitter.split_documents(docs)
        
        elif ext in ["xlsx", "xls", "csv"]:
            # Traitement des fichiers Excel et CSV
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
        
# Chargement de documents (avec gestion OCR)
if st.session_state.role in ("admin", "super_user"):
    with st.expander("📁 Chargement de nouveaux documents", expanded=False):
        st.info("ℹ️ Formats acceptés : PDF, Excel (.xlsx, .xls), CSV, Texte (.txt)")
        st.info("📄 Les PDFs scannés sont automatiquement traités par OCR (Tesseract)")
        
        uploaded_files = st.file_uploader(
            "Sélectionnez un ou plusieurs fichiers",
            type=["pdf", "xlsx", "xls", "csv", "txt"],
            accept_multiple_files=True,
            help="Vous pouvez charger plusieurs fichiers à la fois"
        )
        
        if uploaded_files:
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("➕ Ajouter à la base", type="primary", use_container_width=True):
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
                                uploader = f"{st.session_state.nom} {st.session_state.prenom}"
                                
                                for d in docs:
                                    d.metadata.update({
                                        "doc_id": doc_id,
                                        "filename": uploaded_file.name,
                                        "date_added": date_str,
                                        "uploaded_by_role": st.session_state.role,
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
                        progress_bar.progress((idx + 1) / len(uploaded_files))
                    
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