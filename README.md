# ClaudeMcpPoc

A simple Flask app to upload PDF resumes, extract basic information with spaCy and PyMuPDF, and store results in MongoDB. Includes an MCP (Model Context Protocol) server `resume_analyzer_mcp.py` to query and analyze stored resumes.

## Features
- Upload PDF resumes via POST /upload
- Extracts name, email, phone, skills, education, and summary
- Stores results in MongoDB (resumes_db.candidates)
- List stored resumes via GET /resumes
- MCP server tools for advanced queries and analysis

## Requirements
- Python 3.10+
- MongoDB running locally (default URI mongodb://localhost:27017)
- spaCy English model en_core_web_sm

## Setup
```powershell
# From project root
python -m venv .venv
. .venv\Scripts\Activate.ps1
pip install -U pip
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

## Run the Flask app
```powershell
$env:FLASK_APP = "app.py"
python app.py
```
Then open http://127.0.0.1:5000/.

## Run the MCP server
```powershell
. .venv\Scripts\Activate.ps1
python resume_analyzer_mcp.py
```
The server starts on stdio; integrate per your MCP client.

## Configuration
- MongoDB connection can be customized with environment variables:
  - MONGODB_URI (default mongodb://localhost:27017)
  - DATABASE_NAME (default resumes_db)
  - COLLECTION_NAME (default candidates)

## Notes
- No HTTP wrapper is used.
- Ensure only PDF files are uploaded. Temporary uploaded files are cleaned up after processing.

## Publish to GitHub
If Git and GitHub CLI are installed, you can create the repo and push from PowerShell:
```powershell
# Install Git (if missing)
winget install --id Git.Git -e --source winget

# Install GitHub CLI (optional but recommended)
winget install --id GitHub.cli -e --source winget

# Initialize and push
git init
git add .
git commit -m "Initial commit"
# Authenticate with GitHub CLI (follow prompts)
gh auth login --hostname github.com --git-protocol https --web
# Create a repo named ClaudeMcpPoc under your account and push
gh repo create ClaudeMcpPoc --private --source . --remote origin --push
```
Alternatively, create an empty repo named ClaudeMcpPoc on GitHub, then:
```powershell
git init
git remote add origin https://github.com/<your-username>/ClaudeMcpPoc.git
git add .
git commit -m "Initial commit"
git branch -M main
git push -u origin main
```
