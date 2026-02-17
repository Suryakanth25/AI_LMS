# Migration Guide: AI_LMS

This guide explains how to move your project to a new system while ensuring everything works perfectly.

## Option 1: Git (Recommended for Code)
Since your system currently doesn't have `git` in the terminal path, you would need to install it first.
1. **Install Git**: Download from [git-scm.com](https://git-scm.com/).
2. **Push Code**: Use a service like GitHub or GitLab. 
   - I have already created a `.gitignore` in your root folder. This ensures you don't push 1GB of "noise" (like `node_modules`).
3. **Manual Data**: Push only the code. You **MUST** manually copy the `council.db` and `uploads/` folder to the new system.

## Option 2: Zipping (The "Snapshot" Way)
If you want a single file to move, follow these steps to keep the size small:
1. **Delete node_modules**: In `frontend/`, delete the `node_modules` folder (this takes up 90% of the space and is easy to reinstall).
2. **Zip the rest**: Zip the `council-prototype` folder.
3. **Move and Unzip**: On the new system, unzip it.

## Critical Data Checklist
Regardless of how you move the code, these folders/files are your "Data":
- `backend/council.db`: Your entire database (subjects, questions, etc.).
- `backend/uploads/`: All your PDF/Docx files.
- `backend/chromadb_data/`: Your AI "Memory" (can be rebuilt using the Re-Index tool, but good to keep).

## On the New System
1. **Ollama**: Install Ollama and pull these models:
   ```bash
   ollama pull phi3.5
   ollama pull gemma2:2b
   ollama pull qwen2.5:3b
   ```
2. **Backend**:
   ```bash
   cd backend
   pip install -r requirements.txt
   python main.py
   ```
3. **Frontend**:
   ```bash
   cd frontend
   npm install
   npx expo start
   ```

## Final Step: Re-Index RAG
Once everything is running, call the re-index tool I built for you to ensure the AI "remembers" all your files:
`POST http://localhost:8000/api/tools/reindex-subject/{subject_id}`
