from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import app.services.research

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/research", response_class=HTMLResponse)
async def research_page(request: Request, query: str = Query(...)):
    research_html = await app.services.research.run_deep_research(query)
    return templates.TemplateResponse(
        "research.html",
        {"request": request, "query": query, "research_html": research_html}
    )
