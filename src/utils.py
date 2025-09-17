import time

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

def chat_stream(response):
    for char in response:
        yield char
        time.sleep(0.02)