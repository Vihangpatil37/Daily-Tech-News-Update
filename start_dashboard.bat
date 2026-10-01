@echo off
echo =======================================================
echo Starting Tech News Dashboard V3
echo =======================================================
echo.
echo Make sure you have added your GEMINI_API_KEY to the .env file!
echo.
echo Starting FastAPI Server...
python -m uvicorn app.web.server:app --host 127.0.0.1 --port 8000 --reload
pause
