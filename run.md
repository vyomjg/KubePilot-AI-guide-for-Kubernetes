Terminal 1 — backend
cd C:\Vyom\Projects\RAG
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000

Terminal 2 — web UI
cd C:\Vyom\Projects\RAG
.\.venv\Scripts\streamlit.exe run ui\app.py --server.port 8501 --server.address 0.0.0.0