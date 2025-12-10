import streamlit as st
import time
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.chat_models import ChatOllama
from langchain.prompts import PromptTemplate
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import FlashrankRerank
from langchain.chains import RetrievalQA

PERSIST_DIR = "./chroma_db"
MODEL_NAME = "llama3"

@st.cache_resource
def setup_rag():
    embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    vector_db = Chroma(persist_directory=PERSIST_DIR, embedding_function=embedding_model)
    
    base_retriever = vector_db.as_retriever(
        search_type="mmr", 
        search_kwargs={"k": 25, "fetch_k": 50}
    )
    
    compressor = FlashrankRerank(top_n=8)
    compression_retriever = ContextualCompressionRetriever(
        base_compressor=compressor, 
        base_retriever=base_retriever
    )
    
    llama3_template = """<|begin_of_text|><|start_header_id|>system<|end_header_id|>

You are a technical expert for the Nielsen Engineering Portal. 
Your goal is to provide a comprehensive answer using the context below.

Rules:
1. Combine information from multiple chunks if necessary.
2. If the context has a table, read it carefully row by row.
3. If the context mentions an Image Description, describe it.
4. If the answer is not in the context, say "I don't have enough information."

<|eot_id|><|start_header_id|>user<|end_header_id|>

Context:
{context}

Question: 
{question}

<|eot_id|><|start_header_id|>assistant<|end_header_id|>"""
    
    prompt = PromptTemplate(template=llama3_template, input_variables=["context", "question"])
    llm = ChatOllama(model=MODEL_NAME, temperature=0, keep_alive="5m", num_ctx=4096)
    
    return RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=compression_retriever,
        return_source_documents=True,
        chain_type_kwargs={"prompt": prompt}
    )

def format_source(doc):
    meta = doc.metadata
    type_ = meta.get('type', 'unknown')
    parent = meta.get('parent_page_title', 'Untitled Page')
    
    if type_ == 'image':
        return f"[Image] {meta.get('image_name')}"
    elif type_ == 'attachment':
        return f"[File] {meta.get('source')} (Sheet/Slide: {meta.get('sheet') or meta.get('slide')})"
    return f"[Page] {parent}"

# UI
st.set_page_config(page_title="AskConfluence", page_icon="🤖", layout="wide")

col1, col2, col3 = st.columns([1, 1.5, 1])
with col2:
    st.markdown("<h1 style='text-align: center;'>🤖 AskConfluence</h1>", unsafe_allow_html=True)
    st.image("AskConfluence.png")
    st.markdown("<p style='text-align: center;'>AI-Powered Confluence Knowledge Assistant</p>", unsafe_allow_html=True)

st.divider()

if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "sources" in message:
            with st.expander("📚 Sources"):
                for source in message["sources"]:
                    st.markdown(f"• {source}")

# Chat input
if query := st.chat_input("Ask a question about your Confluence docs..."):
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)
    
    with st.chat_message("assistant"):
        with st.spinner("Searching & reranking..."):
            try:
                qa_system = setup_rag()
                start = time.time()
                response = qa_system.invoke({"query": query})
                elapsed = round(time.time() - start, 2)
                
                answer = f"{response['result']}\n\n*Response time: {elapsed}s*"
                st.markdown(answer)
                
                sources = []
                seen = set()
                for doc in response['source_documents']:
                    citation = format_source(doc)
                    if citation not in seen:
                        sources.append(citation)
                        seen.add(citation)
                
                if sources:
                    with st.expander("📚 Sources"):
                        for source in sources:
                            st.markdown(f"• {source}")
                
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": answer,
                    "sources": sources
                })
            except Exception as e:
                st.error(f"Error: {e}")
