from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Depends
from app.web.auth import verify_credentials
from app.web.ui_routes import router as ui_router
from app.web.research_routes import router as research_router

app = FastAPI(
    title="Tech Intelligence API",
    dependencies=[Depends(verify_credentials)]
)

app.include_router(ui_router)
app.include_router(research_router)
