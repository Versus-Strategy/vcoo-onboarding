from pydantic import BaseModel
from typing import Optional

class VCOOCreate(BaseModel):
    name: Optional[str]

class VCOOState(BaseModel):
    id: str
    name: Optional[str]
    created_at: Optional[str]
    integrations: Optional[str]
