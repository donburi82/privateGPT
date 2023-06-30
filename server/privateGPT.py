from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from langchain.chains import RetrievalQA
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.vectorstores import Chroma
from langchain.llms import GPT4All
import os
import glob
from typing import List
import time

from langchain.document_loaders import (
    CSVLoader,
    EverNoteLoader,
    PyMuPDFLoader,
    TextLoader,
    UnstructuredEmailLoader,
    UnstructuredEPubLoader,
    UnstructuredHTMLLoader,
    UnstructuredMarkdownLoader,
    UnstructuredODTLoader,
    UnstructuredPowerPointLoader,
    UnstructuredWordDocumentLoader,
)

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import Chroma
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.docstore.document import Document
from constants import CHROMA_SETTINGS

app = Flask(__name__)
CORS(app)

load_dotenv()

embeddings_model_name = os.environ.get("EMBEDDINGS_MODEL_NAME")
persist_directory = os.environ.get('PERSIST_DIRECTORY')

llm = None

from constants import CHROMA_SETTINGS

class MyElmLoader(UnstructuredEmailLoader):
    """Wrapper to fallback to text/plain when default does not work"""

    def load(self) -> List[Document]:
        """Wrapper adding fallback for elm without html"""
        try:
            try:
                doc = UnstructuredEmailLoader.load(self)
            except ValueError as e:
                if 'text/html content not found in email' in str(e):
                    # Try plain text
                    self.unstructured_kwargs["content_source"]="text/plain"
                    doc = UnstructuredEmailLoader.load(self)
                else:
                    raise
        except Exception as e:
            # Add file_path to exception message
            raise type(e)(f"{self.file_path}: {e}") from e

        return doc


# Map file extensions to document loaders and their arguments
LOADER_MAPPING = {
    ".csv": (CSVLoader, {}),
    # ".docx": (Docx2txtLoader, {}),
    ".doc": (UnstructuredWordDocumentLoader, {}),
    ".docx": (UnstructuredWordDocumentLoader, {}),
    ".enex": (EverNoteLoader, {}),
    ".eml": (MyElmLoader, {}),
    ".epub": (UnstructuredEPubLoader, {}),
    ".html": (UnstructuredHTMLLoader, {}),
    ".md": (UnstructuredMarkdownLoader, {}),
    ".odt": (UnstructuredODTLoader, {}),
    ".pdf": (PyMuPDFLoader, {}),
    ".ppt": (UnstructuredPowerPointLoader, {}),
    ".pptx": (UnstructuredPowerPointLoader, {}),
    ".txt": (TextLoader, {"encoding": "utf8"}),
    # Add more mappings for other file extensions and loaders as needed
}


def load_single_document(file_path: str) -> Document:
    ext = "." + file_path.rsplit(".", 1)[-1]
    if ext in LOADER_MAPPING:
        loader_class, loader_args = LOADER_MAPPING[ext]
        loader = loader_class(file_path, **loader_args)
        return loader.load()[0]

    raise ValueError(f"Unsupported file extension '{ext}'")


def load_documents(source_dir: str) -> List[Document]:
    # Loads all documents from source documents directory
    all_files = []
    for ext in LOADER_MAPPING:
        all_files.extend(
            glob.glob(os.path.join(source_dir, f"**/*{ext}"), recursive=True)
        )
    return [load_single_document(file_path) for file_path in all_files]

@app.route('/ingest', methods=['GET'])
def ingest_data():
    source_directory = 'source_documents'

    # Load documents and split in chunks
    print(f"Loading documents from {source_directory}")
    chunk_size = 500
    chunk_overlap = 50
    documents = load_documents(source_directory)
    print(f"Loaded {len(documents)} new documents from {source_directory}")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    texts = text_splitter.split_documents(documents)
    print(f"Split into {len(texts)} chunks of text (max. {chunk_size} tokens each)")

    # Create embeddings
    embeddings = HuggingFaceEmbeddings(model_name=embeddings_model_name, cache_folder='models')
    
    # Create and store locally vectorstore
    start = time.time()
    db = Chroma.from_documents(texts, embeddings, persist_directory=persist_directory, client_settings=CHROMA_SETTINGS)
    db.persist()
    db = None
    print()
    print(f"Took {time.time()-start} seconds to ingest the documents.")
    return jsonify(response="Success")
    
@app.route('/get_answer', methods=['POST'])
def get_answer():
    query = request.json
    embeddings = HuggingFaceEmbeddings(model_name=embeddings_model_name)
    db = Chroma(persist_directory=persist_directory, embedding_function=embeddings, client_settings=CHROMA_SETTINGS)
    # retriever = db.as_retriever() # Took 862.4994068145752 seconds.
    target_source_chunks = int(os.environ.get('TARGET_SOURCE_CHUNKS',4))
    retriever = db.as_retriever(search_kwargs={"k": target_source_chunks}) # Took 67.02264881134033 seconds.
    if llm==None:
        return "Model not downloaded", 400    
    qa = RetrievalQA.from_chain_type(llm=llm, chain_type="stuff", retriever=retriever, return_source_documents=True)
    if query!=None and query!="":
        start = time.time()
        res = qa(query)
        answer, docs = res['result'], res['source_documents']
        print()
        print(f"Took {time.time()-start} seconds to generate an answer.")
        
        source_data =[]
        for document in docs:
            source_data.append({"name": document.metadata["source"], "content": document.page_content})
        print(source_data)


        return jsonify(query=query,answer=answer,source=source_data)

    return "Empty Query",400

@app.route('/upload_doc', methods=['POST'])
def upload_doc():
    if 'document' not in request.files:
        return jsonify(response="No document file found"), 400
    
    document = request.files['document']
    if document.filename == '':
        return jsonify(response="No selected file"), 400

    filename = document.filename
    save_path = os.path.join('source_documents', filename)
    document.save(save_path)

    return jsonify(response="Document upload successful")

@app.route('/view_docs', methods=['GET'])
def view_docs():
    docs = []
    for doc in os.listdir('source_documents'):
        path = os.path.join('source_documents', doc)
        if os.path.isfile(path) and doc!='.DS_Store':
            docs.append(doc)
    print(docs)
    return jsonify(docs)

# @app.route('/source_documents/<filename>', methods=['GET'])
# def download_doc(filename: str):
#     return send_from_directory('source_documents', filename, as_attachment=True)

@app.route('/delete_doc/<filename>', methods=['DELETE'])
def delete_doc(filename: str):
    path = os.path.join('source_documents', filename)
    if os.path.isfile(path)==False:
        print("Non-existant file")
        return jsonify(response="Non-existant file"), 400
    try:
        os.remove(path)
        print(f"Removed file {filename}")
        return jsonify(response="Document deletion successful")
    except Exception as e:
        print(e)
        return f"Error in deleting file: {e}", 400

def load_model():
    model_n_ctx = os.environ.get('MODEL_N_CTX')
    model_n_batch = int(os.environ.get('MODEL_N_BATCH',8))
    filename = 'ggml-wizard-13b-uncensored.bin'  # Specify the name for the downloaded file
    models_folder = 'models'  # Specify the name of the folder inside the Flask app root
    file_path = f'{models_folder}/{filename}'
    if os.path.exists(file_path):
        global llm
        callbacks = [StreamingStdOutCallbackHandler()]
        llm = GPT4All(model=file_path, n_ctx=model_n_ctx, backend='gptj', n_batch=model_n_batch, callbacks=callbacks, verbose=False)

if __name__ == "__main__":
  load_model()
  print("LLM0", llm)
  app.run(host="0.0.0.0", debug = False)