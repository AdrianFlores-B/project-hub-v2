from fastapi import FastAPI

from app.routers import auth, projects

app = FastAPI(title="Project Hub")
app.include_router(auth.router)
app.include_router(projects.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
