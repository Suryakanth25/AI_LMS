# Migration Guide: Moving to Council Prototype 🚀

This guide explains how to migrate from the old web-based system to the new **Council Prototype** on a new machine.

## 1. Codebase Setup
Clone the official repository from GitHub:
```bash
git clone https://github.com/Suryakanth25/AI_LMS.git
cd AI_LMS/council-prototype
```

## 2. AI Intelligence (Ollama)
The brain of the system relies on locally running LLMs. Install [Ollama](https://ollama.com/) and download these specific models:

1. **Logician/Chairman**: `ollama pull phi3.5` (or `llama3.2` for HP Victus)
2. **Creative Agent**: `ollama pull gemma2:2b`
3. **Technician Agent**: `ollama pull qwen2.5:3b`

> [!TIP]
> Use `llama3.2` if the HP Victus GPU (4GB) is limited on memory, as it is very efficient.

## 3. Data Migration (Critical)
Git does not store your private data. You **MUST** manually copy these from your old system's `backend/` folder:

- **`council.db`**: Your entire database (subjects, rubrics, questions).
- **`uploads/` folder**: All uploaded study materials/PDFs.
- **`chromadb_data/`**: (Optional) Your RAG vector memory. If you don't copy this, use the Re-Index tool in the Dashboard.

## 4. Backend Setup
1. Open a terminal in `backend/`.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Start the server:
   ```bash
   python main.py
   ```

## 5. Frontend Setup
1. Open a terminal in `frontend/`.
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the mobile environment:
   ```bash
   npx expo start --clear
   ```

---
### Re-Indexing (If materials don't load)
If you see your subjects but no "Study Content" is found during generation, trigger a re-index:
- Go to **Dashboard** -> **Subject** -> Tap **Re-Index** (or use the API tool).
