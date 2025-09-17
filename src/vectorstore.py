from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from src import CONFIG

OPENAI_API_KEY = CONFIG["OPENAI_API_KEY"]
BASE_DIR = "./collections"

embeddings = OpenAIEmbeddings(api_key=OPENAI_API_KEY)

# Une seule collection
def get_vector_store():
    return Chroma(
        collection_name="knowledge_base",
        embedding_function=embeddings,
        persist_directory=BASE_DIR
    )
