# Confluence Data Extraction & Asset Management

Complete pipeline for extracting Confluence pages, downloading linked assets, and preparing data for vector database ingestion.

## Setup

### 1. Install Dependencies
```bash
pip install langchain langchain-community atlassian-python-api google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client boto3 requests pillow
```

### 2. Environment Variables
```bash
export CONFLUENCE_USERNAME="your.email@nielsen.com"
export CONFLUENCE_API_KEY="your_confluence_api_key"
```

### 3. Google Drive API Setup (for Drive files)
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project and enable Google Drive API
3. Create OAuth 2.0 credentials (Desktop app)
4. Download as `credentials.json` in the project folder

## Usage

### Step 1: Extract Confluence Pages
```bash
python DataExtraction.py
```
**Output:**
- `confluence_data_full_withmarkdown.pkl` - All page content with code blocks
- `google_drive_links.json` - List of Google Drive links found
- `valid_pages_markdown.json` - Page metadata

### Step 2: Download Google Drive Files
```bash
python download_drive_files.py
```
**Output:**
- `assets/` - Downloaded Drive files (.xlsx, .docx, .pptx)
- `assets/drive_files_metadata.json` - Metadata mapping files to source pages

### Step 3: Download Confluence Images
```bash
python download_confluence_images.py
```
**Output:**
- `assets/images/` - Downloaded images
- `assets/images_metadata.json` - Metadata mapping images to source pages

### Step 4: Generate Image Captions (Optional but Recommended)
```bash
python generate_image_captions.py
```
**Output:**
- `assets/image_captions.json` - AI-generated captions with page context

## Features

### DataExtraction.py
- ✅ Extracts Confluence pages with markdown formatting
- ✅ Extracts code blocks from Confluence storage format
- ✅ Identifies and logs Google Drive links (Docs, Sheets, Slides)
- ✅ Caches data for incremental updates
- ✅ Filters out retrospectives and sprint pages

### download_drive_files.py
- ✅ Downloads Google Docs as .docx
- ✅ Downloads Google Sheets as .xlsx
- ✅ Downloads Google Slides as .pptx
- ✅ Downloads generic Drive files
- ✅ Tracks metadata (page_id, page_title, source_url)

### download_confluence_images.py
- ✅ Extracts images from Confluence pages
- ✅ Downloads with authentication
- ✅ Tracks metadata for vector DB ingestion

### generate_image_captions.py
- ✅ Uses AWS Bedrock (Claude 3 Sonnet) for image analysis
- ✅ Generates technical descriptions
- ✅ Includes page context for better captions
- ✅ Superior to OCR for diagrams and screenshots

## Data Structure

All assets include metadata for tracing back to source:
```json
{
  "local_path": "assets/file.xlsx",
  "original_url": "https://docs.google.com/...",
  "file_type": "Google Sheet",
  "page_id": "103654924",
  "page_title": "R7 2021-Global",
  "source_url": "https://nielsen.atlassian.net/..."
}
```

## Next Steps

Use the generated data for vector database ingestion with preserved metadata for source attribution during retrieval.
