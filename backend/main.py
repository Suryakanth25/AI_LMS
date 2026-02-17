import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base
from routers import subjects, generation, vetting, benchmarks, outcomes, training, tools

app = FastAPI(title="The Council API", version="1.0.0")

import logging
import traceback
from fastapi import Request
from fastapi.responses import JSONResponse

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global Exception: {exc}")
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"message": "Internal Server Error", "detail": str(exc)},
    )


@app.on_event("startup")
def startup():
    os.makedirs("./uploads", exist_ok=True)
    Base.metadata.create_all(bind=engine)


# Routers
app.include_router(subjects.router)
app.include_router(outcomes.router)
app.include_router(generation.router)
app.include_router(vetting.router, prefix="/api/vetting", tags=["Vetting"])
app.include_router(benchmarks.router)
app.include_router(training.router, prefix="/api/training", tags=["Training"])
app.include_router(tools.router)


@app.get("/")
def root():
    return {"message": "The Council API is running", "version": "1.0.0"}


@app.get("/health")
def health():
    return {"status": "ok"}
