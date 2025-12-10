import pickle
import os

def load_pickle(file_path):
    if not os.path.exists(file_path):
        print(f"Warning: {file_path} not found")
        return []
    
    with open(file_path, 'rb') as f:
        data = pickle.load(f)
    print(f"Loaded {len(data)} items from {file_path}")
    return data

def main():
    # Load all pickle files
    confluence_data = load_pickle('confluence_data_full_withmarkdown.pkl')
    drive_documents = load_pickle('drive_documents_parsed.pkl')
    
    # Check for image data (optional)
    image_data = []
    if os.path.exists('image_documents_parsed.pkl'):
        image_data = load_pickle('image_documents_parsed.pkl')
    
    # Combine all data
    combined_data = []
    
    # Add confluence pages
    for item in confluence_data:
        combined_data.append({
            'page_id': item.get('metadata', {}).get('id', ''),
            'page_title': item.get('metadata', {}).get('title', ''),
            'source_url': item.get('metadata', {}).get('source', ''),
            'content': item.get('page_content', ''),
            'type': 'confluence_page',
            'metadata': item.get('metadata', {})
        })
    
    # Add drive documents
    for item in drive_documents:
        combined_data.append({
            'page_id': item.get('page_id', ''),
            'page_title': item.get('page_title', ''),
            'source_url': item.get('source_url', ''),
            'content': item.get('content', ''),
            'type': 'drive_document',
            'file_type': item.get('file_type', ''),
            'metadata': item.get('metadata', {})
        })
    
    # Add image data if available
    for item in image_data:
        combined_data.append({
            'page_id': item.get('page_id', ''),
            'page_title': item.get('page_title', ''),
            'source_url': item.get('source_url', ''),
            'content': item.get('caption', ''),
            'type': 'image',
            'metadata': item.get('metadata', {})
        })
    
    # Sort by page_id
    combined_data.sort(key=lambda x: x.get('page_id', ''))
    
    # Save combined data
    with open('combined_confluence_data.pkl', 'wb') as f:
        pickle.dump(combined_data, f)
    
    print(f"\nCombined {len(combined_data)} total items:")
    print(f"  - Confluence pages: {len(confluence_data)}")
    print(f"  - Drive documents: {len(drive_documents)}")
    print(f"  - Images: {len(image_data)}")
    print(f"\nSaved to: combined_confluence_data.pkl")

if __name__ == '__main__':
    main()
