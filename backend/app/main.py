from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models
from .database import Base, engine
from .routers import criteria, records, scoring
from .seed import run_seed

app = FastAPI(title="CallMetrics API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(criteria.router)
app.include_router(records.router)
app.include_router(scoring.router)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    run_seed.run()


@app.get("/api/health")
def health():
    return {"status": "ok"}
