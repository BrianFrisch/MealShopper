$host.UI.RawUI.WindowTitle = "Shopper Service"
python -m uvicorn main:app --app-dir apps/shopper-domain --port 8001 --reload