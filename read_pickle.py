import pickle

def read_pickle(file_path, show_page_id=None):
    with open(file_path, 'rb') as f:
        data = pickle.load(f)
    
    print(f"Total items: {len(data)}")
    
    if show_page_id:
        # Find and show complete entry for specific page_id
        for item in data:
            # confluence_data uses 'id', corpus uses 'parent_page_id'
            page_id = item.metadata.get('id') or item.metadata.get('parent_page_id')
            if str(page_id) == str(show_page_id):
                print(f"\n=== COMPLETE ENTRY FOR PAGE_ID: {page_id} ===")
                print(f"Content: {item.page_content}")
                print(f"Metadata: {item.metadata}")
                return
        print(f"Page ID {show_page_id} not found")
    else:
        # Show first few items
        for i, item in enumerate(data[:2]):
            page_id = item.metadata.get('id') or item.metadata.get('parent_page_id', 'N/A')
            print(f"\nItem {i+1} - Page ID: {page_id}")
            print(f"Content preview: {item.page_content}...")
            print(f"Metadata: {item.metadata}...")

# Usage:
print("=== COMBINED FILE ===")
read_pickle('combined_confluence_data.pkl', show_page_id='103610292')

print("\n=== CORPUS FILE ===")
read_pickle('corpus.pkl', show_page_id='103610292')

print("\n=== CONFLUENCE FILE ===")
read_pickle('confluence_data_full_withmarkdown.pkl', show_page_id='103610292')
