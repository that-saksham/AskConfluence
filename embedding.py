import pickle
import os
import shutil
from langchain.text_splitter import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter
from langchain.schema import Document
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

# --- CONFIGURATION ---
INPUT_FILE = 'confluence_data_enriched.pkl'
PERSIST_DIR = "./chroma_db"

def to_dict(obj):
    """Helper to convert Pydantic/Objects to a standard dictionary."""
    if isinstance(obj, dict):
        return obj
    # Check for Pydantic v1 (.dict()) or v2 (.model_dump())
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    # Fallback: try standard attribute dict
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return {}

def ingest_nested_data():
    print(f"--- 🚀 Starting Ingestion for Nested Structure ---")
    
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Error: {INPUT_FILE} not found.")
        return

    with open(INPUT_FILE, 'rb') as f:
        raw_data = pickle.load(f)
    
    print(f"✅ Loaded {len(raw_data)} items.")

    # --- SETUP SPLITTERS ---
    headers = [("#", "Header 1"), ("##", "Header 2"), ("###", "Header 3")]
    md_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers)
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=512,
        chunk_overlap=64,
        separators=["\n\n", "\n", " ", ""]
    )

    final_chunks = []

    # --- PROCESSING LOOP ---
    for raw_item in raw_data:
        # 1. Convert Object to Dictionary (The Fix)
        item = to_dict(raw_item)
        
        # 2. Extract Metadata
        original_meta = item.get('metadata', {})
        if not original_meta:
            # Sometimes metadata is flattened in the object
            original_meta = item 
        
        # Clean metadata for Chroma (remove nested lists)
        parent_meta = {
            k: v for k, v in original_meta.items() 
            if k not in ['attachments', 'images', 'links', 'page-content', 'page_content']
        }
        
        # Normalize keys (handle 'id' vs 'page_id')
        parent_meta['parent_page_id'] = str(original_meta.get('id', 'unknown'))
        parent_meta['parent_page_title'] = original_meta.get('title', 'Untitled')
        parent_meta['type'] = 'page'

        # --- A. PROCESS PAGE CONTENT ---
        # Handle both "page-content" (JSON style) and "page_content" (Python style)
        page_content = item.get('page-content') or item.get('page_content') or ''
        
        if page_content and str(page_content).strip():
            md_splits = md_splitter.split_text(str(page_content))
            for split in md_splits:
                combined_meta = {**parent_meta, **split.metadata, 'content_source': 'confluence_body'}
                final_chunks.append(Document(page_content=split.page_content, metadata=combined_meta))

        # --- B. PROCESS NESTED ATTACHMENTS ---
        # Access attachments safely
        attachments = original_meta.get('attachments', [])
        for att in attachments:
            # Handle if attachment is also an object
            att = to_dict(att)
            
            att_content = att.get('content', '')
            if att_content and str(att_content).strip():
                att_meta = {
                    **parent_meta,
                    'source': att.get('source', 'unknown_file'),
                    'file_type': att.get('file_type', 'unknown'),
                    'type': 'attachment',
                    'content_source': 'attachment'
                }
                # Chunk it
                att_chunks = text_splitter.create_documents([str(att_content)], metadatas=[att_meta])
                final_chunks.extend(att_chunks)

        # --- C. PROCESS NESTED IMAGES ---
        images = original_meta.get('images', [])
        for i, img in enumerate(images):
            img = to_dict(img)
            
            summary = img.get('summary', '')
            if summary and str(summary).strip():
                img_meta = {
                    **parent_meta,
                    'image_name': img.get('image_name', f'image_{i}'),
                    'type': 'image',
                    'content_source': 'image_summary'
                }
                final_chunks.append(Document(page_content=f"Image Description: {summary}", metadata=img_meta))

    print(f"✅ Processing Complete. Generated {len(final_chunks)} total chunks.")
    
    # --- SAVE TO DB ---
    if len(final_chunks) == 0:
        print("❌ Error: 0 chunks created. Keys might be mismatched.")
        return

    if os.path.exists(PERSIST_DIR):
        shutil.rmtree(PERSIST_DIR)
        print("   Cleared old database.")

    print("   Embedding and Indexing...")
    embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    vector_db = Chroma.from_documents(
        documents=final_chunks,
        embedding=embedding_model,
        persist_directory=PERSIST_DIR
    )
    
    print(f"🎉 SUCCESS! Database saved to '{PERSIST_DIR}'")

if __name__ == "__main__":
    ingest_nested_data()