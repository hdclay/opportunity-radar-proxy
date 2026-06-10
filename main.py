from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

USA_SPENDING_BASE = "https://api.usaspending.gov/api/v2"

class ProxyBody(BaseModel):
    path: str        # e.g. "/search/spending_by_award/"
    payload: dict    # the POST body to forward


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
