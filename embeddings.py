from langchain_ollama import OllamaLLM
from langchain_ollama import OllamaEmbeddings
import os
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import FAISS
from fastapi import FastAPI, UploadFile, File,Form
from pydantic import BaseModel
from langchain_core.prompts import ChatPromptTemplate
from pathlib import Path
from langchain_huggingface import HuggingFaceEmbeddings
"""prompt_template=ChatPromptTemplate(template= You are a database assistant.

The user will ask a question about the business database.

Use ONLY the database schema information provided in the context.

Your job is to identify the tables and columns relevant to the user's question.

Context:
{context}

User question:
{question}

Instructions:
1. Identify the relevant tables.
2. Identify the relevant columns.
3. Explain how the tables are related if relationships are available.
4. Do not invent tables or columns.
5. Do not generate SQL yet.
6. If the required information is not present in the context, say so.

Relevant database information:
) """
"""data=TextLoader("business_table_catalog.txt",encoding="utf-8")
data=data.load()
splitter=RecursiveCharacterTextSplitter(chunk_size=1000,chunk_overlap=200)
chunks=splitter.split_documents(data)
embeddings=OllamaEmbeddings(model="nomic-embed-text")
output_dir="faiss_index" """
base_dir = Path(__file__).resolve().parent
HF_HOME = Path(os.getenv("HF_HOME", base_dir / ".cache" / "huggingface"))
if not HF_HOME.is_absolute():
    HF_HOME = base_dir / HF_HOME
os.environ["HF_HOME"] = str(HF_HOME)
HF_HOME.mkdir(parents=True, exist_ok=True)

documents=[]
data_location = Path(os.getenv("TABLE_CATALOG_PATH", base_dir / "business_table_catalog"))
if not data_location.is_absolute():
    data_location = base_dir / data_location
db_location = Path(os.getenv("FAISS_INDEX_PATH", base_dir / "faiss_index"))
if not db_location.is_absolute():
    db_location = base_dir / db_location
for path in data_location.glob("*.txt"):
    loader=TextLoader(str(path),encoding="utf-8")
    docs=loader.load()
    for doc in docs:
        doc.metadata["table"]=path.stem
        doc.metadata["source"] = path.relative_to(base_dir).as_posix()
    documents.extend(docs)
splitter=RecursiveCharacterTextSplitter(chunk_size=700,chunk_overlap=200)
chunks=splitter.split_documents(documents)
embeddings=HuggingFaceEmbeddings(model="sentence-transformers/all-MiniLM-L6-v2")
vectorstore=FAISS.from_documents(chunks, embeddings
)
vectorstore.save_local(str(db_location))