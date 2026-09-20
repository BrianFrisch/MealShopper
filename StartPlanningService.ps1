$host.UI.RawUI.WindowTitle = "Planning Service"
python -m uvicorn main:app --app-dir apps/planning-domain --port 8002 --reload