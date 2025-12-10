import json
import os
import pickle
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

def authenticate():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    return build('drive', 'v3', credentials=creds)

def extract_file_id(url):
    if '/d/' in url:
        return url.split('/d/')[1].split('/')[0]
    elif 'id=' in url:
        return url.split('id=')[1].split('&')[0]
    return None

def download_file(service, file_id, file_type, output_path):
    mime_types = {
        'Google Doc': ('application/vnd.openxmlformats-officedocument.wordprocessingml.document', '.docx'),
        'Google Sheet': ('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', '.xlsx'),
        'Google Slide': ('application/vnd.openxmlformats-officedocument.presentationml.presentation', '.pptx')
    }
    
    try:
        if file_type in mime_types:
            mime_type, ext = mime_types[file_type]
            request = service.files().export_media(fileId=file_id, mimeType=mime_type)
            output_path = output_path.replace('.bin', ext)
        else:
            request = service.files().get_media(fileId=file_id)
        
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        
        with open(output_path, 'wb') as f:
            f.write(fh.getvalue())
        return output_path
    except Exception as e:
        print(f"Error downloading {file_id}: {e}")
        return None

def main():
    with open('google_drive_links.json', 'r') as f:
        links = json.load(f)
    
    service = authenticate()
    os.makedirs('assets', exist_ok=True)
    
    metadata = []
    for item in links:
        file_id = extract_file_id(item['link_url'])
        if not file_id:
            continue
        
        output_path = f"assets/{file_id}.bin"
        downloaded_path = download_file(service, file_id, item['file_type'], output_path)
        
        if downloaded_path:
            metadata.append({
                'local_path': downloaded_path,
                'original_url': item['link_url'],
                'file_type': item['file_type'],
                'page_id': item['page_id'],
                'page_title': item['page_title'],
                'source_url': item['source_url']
            })
            print(f"Downloaded: {item['page_title']} - {file_id}")
    
    with open('assets/drive_files_metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\nDownloaded {len(metadata)} files")

if __name__ == '__main__':
    main()
