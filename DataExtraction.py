import os
import pickle
import json
import time
import re
from typing import List, Dict
from langchain_community.document_loaders import ConfluenceLoader
from atlassian import Confluence

# --- Configuration ---
CONTENT_CACHE_FILE = "confluence_data_full_withmarkdown.pkl"
METADATA_CACHE_FILE = "valid_pages_markdown.json"
GOOGLE_LINKS_LOG_FILE = "google_drive_links.json"
SPACE_KEY = "SDKDOC"
BATCH_SIZE = 50
SLEEP_TIME = 2

EXCLUDE_KEYWORDS = [
    "Retrospective",
    "Sprint"
]

def get_confluence_client():
    url = "https://nielsen.atlassian.net/wiki"
    username = os.getenv("CONFLUENCE_USERNAME", "dhruv.agarwal@nielsen.com")
    api_key = os.getenv("CONFLUENCE_API_KEY")
    if not api_key: raise ValueError("CONFLUENCE_API_KEY not set")
    return Confluence(url=url, username=username, password=api_key)

def extract_links_from_storage(confluence: Confluence, page_id: str):
    """Extract all links from Confluence storage format"""
    try:
        import html
        page = confluence.get_page_by_id(page_id=page_id, expand='body.storage')
        html_content = page['body']['storage']['value']
        
        links = []
        seen_urls = set()
        
        # --- 1. Improved Anchor Tag Extraction ---
        # This new pattern focuses on extracting the HREF first, regardless of what the link text contains.
        # It finds <a ... href="..."> and then attempts to find the closing </a> 
        # but doesn't strictly require the text to be tag-free.
        anchor_pattern = re.compile(r'<a\s+(?:[^>]*?\s+)?href=["\']([^"\']*)["\']', re.IGNORECASE)
        
        # We assume the text is immediately following the opening tag, but extraction of text 
        # from mixed HTML is complex with regex. For the log, the URL is the priority.
        # We can run a simplified search just for the URLs.
        for url in anchor_pattern.findall(html_content):
            url = html.unescape(url)
            if url not in seen_urls:
                links.append({"text": "Link", "url": url}) # Text is generic here to ensure safety
                seen_urls.add(url)

        # --- 2. Smart Link / Macro Extraction (CRITICAL FOR DRIVE LINKS) ---
        # Catches links stored inside Confluence macros (e.g., <ac:parameter ac:name="url">)
        macro_pattern = re.compile(r'<ac:parameter[^>]+ac:name=["\'](?:url|href|uri)["\'][^>]*>([^<]+)</ac:parameter>', re.IGNORECASE)
        for url in macro_pattern.findall(html_content):
            url = html.unescape(url)
            if url not in seen_urls:
                links.append({"text": "Smart Link", "url": url, "type": "macro"})
                seen_urls.add(url)
        
        # --- 3. HTML Encoded URLs (e.g. <https://...>) ---
        # Catches plain text URLs wrapped in brackets like &lt;https://...&gt;
        # Updated to be slightly more permissible with query params
        encoded_pattern = re.compile(r'<(https?:\/\/.*?)>', re.IGNORECASE)
        for url in encoded_pattern.findall(html_content):
            url = html.unescape(url)
            if url not in seen_urls:
                links.append({"text": url, "url": url})
                seen_urls.add(url)
        
        # --- 4. Confluence Internal Links ---
        internal_pattern = re.compile(r'<ri:page ri:content-title="([^"]+)"', re.IGNORECASE)
        for title in internal_pattern.findall(html_content):
            # Safe check to ensure page/space keys exist
            space_key = confluence.get_page_by_id(page_id).get('space', {}).get('key', SPACE_KEY)
            internal_url = f"https://nielsen.atlassian.net/wiki/spaces/{space_key}/pages/{title}"
            
            if internal_url not in seen_urls:
                links.append({"text": title, "url": internal_url, "type": "internal"})
                seen_urls.add(internal_url)
        
        return links
    except Exception as e:
        print(f"Failed to extract links from {page_id}: {e}")
        return []
def extract_links(docs, confluence):
    """Extract links from docs"""
    for doc in docs:
        page_id = doc.metadata.get('id')
        if page_id:
            doc.metadata['links'] = extract_links_from_storage(confluence, page_id)
    
    return docs

def identify_google_file_type(url: str) -> str:
    """
    Categorizes Google links into specific types:
    Sheets, Docs, Slides, Forms, Drive Folders, or Generic Files (PDFs/Zips).
    """
    url_lower = url.lower()
    
    # 1. Standard Google Office Types
    if "spreadsheets" in url_lower: return "Google Sheet"
    if "document" in url_lower: return "Google Doc"
    if "presentation" in url_lower: return "Google Slide"
    if "forms" in url_lower: return "Google Form"
    if "script.google.com" in url_lower: return "Google App Script"
    if "jamboard" in url_lower: return "Google Jamboard"
    
    # 2. Specific Google Drive Types
    if "drive.google.com" in url_lower:
        if "/folders/" in url_lower: 
            return "Google Drive Folder"
        if "/file/" in url_lower or "/open" in url_lower: 
            # These are often PDFs, Images, Videos, or Zips hosted on Drive
            if ".pdf" in url_lower: return "Google Drive File (PDF)" 
            return "Google Drive File (Generic/Binary)"
        return "Google Drive Link (Generic)"
        
    return "Unknown Google Link"

def update_google_links_log(new_docs: List):
    """
    Scans new docs for Google links and updates the JSON log file.
    """
    existing_data = []
    
    # Load existing data to append rather than overwrite
    if os.path.exists(GOOGLE_LINKS_LOG_FILE):
        try:
            with open(GOOGLE_LINKS_LOG_FILE, 'r') as f:
                existing_data = json.load(f)
        except json.JSONDecodeError:
            existing_data = []

    new_entries = []
    
    for doc in new_docs:
        links = doc.metadata.get('links', [])
        
        for link in links:
            url = link['url']
            
            # --- UPDATED FILTER LOGIC ---
            # Checks for 'docs.google.com' (files) OR 'drive.google.com' (folders/blobs)
            if "google.com" in url and ("docs" in url or "drive" in url):
                
                entry = {
                    "page_id": doc.metadata.get("id"),
                    "page_title": doc.metadata.get("title"),
                    "link_text": link["text"],
                    "link_url": url,
                    "file_type": identify_google_file_type(url),
                    "source_url": doc.metadata.get("source")
                }
                
                # Deduplication check
                if entry not in existing_data and entry not in new_entries:
                    new_entries.append(entry)

    if new_entries:
        print(f"  -> Found {len(new_entries)} new Google links (Drive/Docs/Sheets). Updating log...")
        combined_data = existing_data + new_entries
        with open(GOOGLE_LINKS_LOG_FILE, 'w') as f:
            json.dump(combined_data, f, indent=4)

def get_valid_pages_metadata(confluence: Confluence, space_key: str) -> List[Dict]:
    """Retrieves metadata (ID/Title) for all relevant pages."""
    if os.path.exists(METADATA_CACHE_FILE):
        print(f"Loading metadata from {METADATA_CACHE_FILE}...")
        with open(METADATA_CACHE_FILE, 'r') as f: return json.load(f)

    print(f"Scanning Space '{space_key}' for valid pages...")
    start, limit = 0, 100
    valid_pages = []
    
    while True:
        results = confluence.get_all_pages_from_space(
            space=space_key, start=start, limit=limit, 
            content_type='page', expand=None
        )
        if not results: break
            
        for page in results:
            if not any(k.lower() in page['title'].lower() for k in EXCLUDE_KEYWORDS):
                valid_pages.append({'id': page['id'], 'title': page['title']})
        
        start += limit
        time.sleep(0.5)

    with open(METADATA_CACHE_FILE, 'w') as f: json.dump(valid_pages, f)
    return valid_pages

def load_and_cache_docs():
    confluence = get_confluence_client()
    valid_pages_meta = get_valid_pages_metadata(confluence, SPACE_KEY)
    valid_ids = [p['id'] for p in valid_pages_meta]

    existing_docs = []
    if os.path.exists(CONTENT_CACHE_FILE):
        with open(CONTENT_CACHE_FILE, 'rb') as f: existing_docs = pickle.load(f)

    downloaded_ids = {doc.metadata.get('id') for doc in existing_docs if 'id' in doc.metadata}
    ids_to_download = [pid for pid in valid_ids if pid not in downloaded_ids]
    
    if not ids_to_download:
        print("All pages already cached.")
        return existing_docs

    print(f"Downloading {len(ids_to_download)} new pages...")
    
    loader_base_args = {
        "url": "https://nielsen.atlassian.net/wiki",
        "username": os.getenv("CONFLUENCE_USERNAME", "dhruv.agarwal@nielsen.com"),
        "api_key": os.getenv("CONFLUENCE_API_KEY")
    }

    for i in range(0, len(ids_to_download), BATCH_SIZE):
        batch_ids = ids_to_download[i : i + BATCH_SIZE]
        print(f"Processing batch {i // BATCH_SIZE + 1}...")
        
        try:
            loader = ConfluenceLoader(
                **loader_base_args,
                page_ids=batch_ids,
                include_attachments=False,
                limit=BATCH_SIZE,
                keep_markdown_format=True
            )
            
            new_docs = loader.load()
            
            # 1. Extract links and code blocks
            new_docs = extract_links(new_docs, confluence)
            
            # 2. Filter and log Google Drive links
            update_google_links_log(new_docs)
            
            existing_docs.extend(new_docs)
            
            with open(CONTENT_CACHE_FILE, 'wb') as f: pickle.dump(existing_docs, f)
            time.sleep(SLEEP_TIME)
            
        except Exception as e:
            print(f"Error in batch: {e}")
            break

    return existing_docs

if __name__ == "__main__":
    docs = load_and_cache_docs()
    
    # Verification output
    if os.path.exists(GOOGLE_LINKS_LOG_FILE):
        with open(GOOGLE_LINKS_LOG_FILE, 'r') as f:
            links = json.load(f)
            print(f"\nTotal Google Links Found: {len(links)}")
            
            # Count types for verification
            type_counts = {}
            for link in links:
                t = link['file_type']
                type_counts[t] = type_counts.get(t, 0) + 1
            
            print("Breakdown by Type:")
            for t, count in type_counts.items():
                print(f"  - {t}: {count}")