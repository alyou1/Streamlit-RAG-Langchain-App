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
            
            # === NOUVEAU: Vérification si PDF scanné ===
            if len(docs) == 0 or all(len(doc.page_content.strip()) < 50 for doc in docs):
                st.info("📄 PDF scanné détecté. Application de l'OCR en cours...")
                
                # Extraction du texte avec OCR
                ocr_text = extract_text_from_scanned_pdf(tmp_path)
                
                if ocr_text:
                    # Création d'un fichier texte temporaire
                    txt_path = tmp_path.replace('.pdf', '_ocr.txt')
                    with open(txt_path, 'w', encoding='utf-8') as f:
                        f.write(ocr_text)
                    
                    # Traitement du fichier texte
                    docs = [type("Doc", (), {
                        "page_content": ocr_text,
                        "metadata": {}
                    })]
                    docs = text_splitter.split_documents(docs)
                    
                    # Nettoyage du fichier temporaire
                    os.remove(txt_path)
                else:
                    st.warning("⚠️ Impossible d'extraire le texte du PDF scanné")
            
            # Nettoyage
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


def extract_text_from_scanned_pdf(pdf_path):
    """
    Extrait le texte d'un PDF scanné en utilisant OCR.
    
    Args:
        pdf_path: Chemin vers le fichier PDF
        
    Returns:
        str: Texte extrait de toutes les pages
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
                # Pour chaque image trouvée
                for img_index, img in enumerate(image_list):
                    xref = img[0]
                    base_image = pdf_document.extract_image(xref)
                    image_bytes = base_image["image"]
                    
                    # Convertir en image PIL
                    image = Image.open(io.BytesIO(image_bytes))
                    
                    # Appliquer l'OCR avec Tesseract
                    # Configuration pour améliorer la précision
                    custom_config = r'--oem 3 --psm 6 -l fra+eng'  # français + anglais
                    text = pytesseract.image_to_string(image, config=custom_config)
                    
                    extracted_text.append(text)
            else:
                # Si pas d'images, essayer de rendre la page en image
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # Augmentation de la résolution
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                
                custom_config = r'--oem 3 --psm 6 -l fra+eng'
                text = pytesseract.image_to_string(img, config=custom_config)
                extracted_text.append(text)
        
        pdf_document.close()
        
        # Combiner tout le texte extrait
        full_text = "\n\n".join(extracted_text)
        return full_text.strip()
        
    except Exception as e:
        st.error(f"Erreur lors de l'extraction OCR: {str(e)}")
        return None