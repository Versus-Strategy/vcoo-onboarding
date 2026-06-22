from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .db import engine, Base, SessionLocal
from . import models, crud, schemas, auth

app = FastAPI(title="VCOO Onboarding API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    Base.metadata.create_all(bind=engine)

@app.post("/vcoo")
def create_vcoo():
    vcoo = crud.create_vcoo()
    return {"id": str(vcoo.id)}

@app.get("/vcoo/{vcoo_id}/config-link")
def get_config_link(vcoo_id: str):
    token = auth.create_config_token(vcoo_id)
    return {"url": f"/setup/{token}"}

@app.get("/vcoo/{vcoo_id}/state")
def get_state(vcoo_id: str):
    v = crud.get_vcoo(vcoo_id)
    if not v:
        raise HTTPException(status_code=404, detail="Not found")
    return v.to_dict()

# OAuth placeholders
@app.get("/vcoo/{vcoo_id}/oauth/{provider}/start")
def oauth_start(vcoo_id: str, provider: str):
    # TODO: construir URL del proveedor
    return {"redirect": "https://provider.example/auth?client_id=..."}

@app.get("/vcoo/{vcoo_id}/oauth/{provider}/callback")
def oauth_callback(vcoo_id: str, provider: str, code: str = None):
    # TODO: intercambiar code por token y guardar
    return {"status": "ok"}
