from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=86400,
)

USA_SPENDING_BASE = "https://api.usaspending.gov/api/v2"

class ProxyBody(BaseModel):
    path: str
    payload: dict

@app.options("/api/usaspending")
async def options_handler():
    return JSONResponse(content={}, status_code=200)

@app.post("/api/usaspending")
async def usaspending_proxy(body: ProxyBody):
    url = f"{USA_SPENDING_BASE}{body.path}"
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(url, json=body.payload)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=str(e))
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"USASpending unreachable: {e}")

@app.get("/health")
async def health():
    return {"status": "ok"}
