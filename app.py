import os
import time
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.chat_models import ChatOllama
from langchain.prompts import PromptTemplate
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import FlashrankRerank
from langchain.chains import RetrievalQA

# --- CONFIGURATION ---
PERSIST_DIR = "./chroma_db"
MODEL_NAME = "llama3" 

def setup_advanced_rag():
    print("--- Setting up Advanced RAG (with Reranking) ---")
    
    # 1. Load Embeddings
    print("Loading embedding model...")
    embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    # 2. Load Vector DB
    if not os.path.exists(PERSIST_DIR):
        raise FileNotFoundError(f"Database not found at {PERSIST_DIR}.")
    
    vector_db = Chroma(persist_directory=PERSIST_DIR, embedding_function=embedding_model)
    print(f"Loaded Vector DB with {vector_db._collection.count()} documents.")

    # 3. BASE RETRIEVER (The "Broad Net")
    # Fetch top 25 chunks to ensure we don't miss anything relevant
    base_retriever = vector_db.as_retriever(
        search_type="mmr", 
        search_kwargs={"k": 25, "fetch_k": 50}
    )

    # 4. COMPRESSION RETRIEVER (The "Filter")
    # Reranks the 25 chunks and selects the top 8 most relevant ones
    print("Initializing FlashRank Reranker...")
    compressor = FlashrankRerank(top_n=8)
    
    compression_retriever = ContextualCompressionRetriever(
        base_compressor=compressor, 
        base_retriever=base_retriever
    )

    # 5. Define Prompt (Optimized for Context Heavy Inputs)
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
    
    prompt = PromptTemplate(
        template=llama3_template, 
        input_variables=["context", "question"]
    )

    # 6. Initialize Ollama
    llm = ChatOllama(
        model=MODEL_NAME,
        temperature=0,        
        keep_alive="5m",
        # Increase num_ctx if your machine has RAM (default is 2048, Llama3 supports 8192)
        num_ctx=4096 
    )

    # 7. Build Chain
    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=compression_retriever, # Use the reranker here
        return_source_documents=True,
        chain_type_kwargs={"prompt": prompt}
    )
    
    return qa_chain

def format_source(doc):
    meta = doc.metadata
    type_ = meta.get('type', 'unknown')
    parent = meta.get('parent_page_title', 'Untitled Page')
    
    if type_ == 'image':
        return f"[Image] {meta.get('image_name')}"
    elif type_ == 'attachment':
        return f"[File] {meta.get('source')} (Sheet/Slide: {meta.get('sheet') or meta.get('slide')})"
    return f"[Page] {parent}"

if __name__ == "__main__":
    try:
        qa_system = setup_advanced_rag()
        print("\n✅ Advanced RAG Ready! (Type 'exit' to quit)\n")
        
        while True:
            query = input("You: ")
            if query.lower() in ['exit', 'quit']:
                break
            
            start_time = time.time()
            print("Searching & Reranking...", end="", flush=True)
            
            try:
                response = qa_system.invoke({"query": query})
                end_time = time.time()
                
                print(f"\rAI ({MODEL_NAME}) - {round(end_time - start_time, 2)}s:\n{response['result']}")
                
                print("\n--- Top Relevant Sources (After Reranking) ---")
                seen = set()
                for doc in response['source_documents']:
                    citation = format_source(doc)
                    if citation not in seen:
                        print(f"• {citation}")
                        # Optional: Print relevance score if available
                        if 'relevance_score' in doc.metadata:
                            print(f"  (Score: {doc.metadata['relevance_score']:.4f})")
                        seen.add(citation)
                print("-" * 30 + "\n")
                
            except Exception as e:
                print(f"\nError: {e}")

    except Exception as e:
        print(f"Setup Error: {e}")