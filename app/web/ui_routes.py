from fastapi import APIRouter, Request, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
import os

from app.services.db import get_db_connection
from app.orchestrator import run_pipeline

router = APIRouter()
templates = Jinja2Templates(directory="templates")

SOURCES_FILE = "app/sources.yaml"

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        # Using rowid for ordering to get the latest record
        c.execute("SELECT html_content FROM historical_reports ORDER BY rowid DESC LIMIT 1")
        row = c.fetchone()
    except Exception as e:
        row = None
    finally:
        conn.close()
    
    report_content = row[0] if row else "<p>No report generated yet.</p>"
    return templates.TemplateResponse("dashboard.html", {"request": request, "report_content": report_content})

@router.get("/settings", response_class=PlainTextResponse)
async def get_settings():
    if os.path.exists(SOURCES_FILE):
        with open(SOURCES_FILE, "r") as f:
            return f.read()
    return ""

@router.post("/settings")
async def save_settings(sources_text: str = Form(...)):
    with open(SOURCES_FILE, "w") as f:
        f.write(sources_text)
    return RedirectResponse(url="/", status_code=303)

@router.post("/run")
async def run_pipeline_endpoint(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_pipeline)
    return {"status": "Pipeline started"}
