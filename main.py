from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
import json
import os
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
CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")


class ProxyBody(BaseModel):
    path: str        # e.g. "/search/spending_by_award/"
    payload: dict    # the POST body to forward


class MatchBody(BaseModel):
    description: str


@app.options("/api/usaspending")
@app.options("/api/match-naics")
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


@app.post("/api/match-naics")
async def match_naics(body: MatchBody):
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured on server")

    system_prompt = (
        "You are a federal procurement expert. Given a business description, "
        "return ONLY a JSON object with no markdown, no explanation, no code fences. "
        'Format: {"naics_codes": ["XXXXXX", ...], "label": "short business type label", '
        '"agencies": ["Agency 1", "Agency 2", "Agency 3", "Agency 4"]}. '
        "Return 4-6 of the most relevant 6-digit NAICS codes and 3-4 federal agencies "
        "that realistically buy from this type of business. "
        "If the description is too vague, nonsensical, or not a real business "
        '(e.g. random words, jokes, gibberish), return {"naics_codes": [], "label": "", "agencies": []}.'
    )

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(
                CLAUDE_API_URL,
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": "claude-sonnet-4-5",
                    "max_tokens": 500,
                    "system": system_prompt,
                    "messages": [
                        {"role": "user", "content": f"Business description: {body.description}"}
                    ],
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=str(e))
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Claude API unreachable: {e}")

    # Extract text block from Claude's response
    text = ""
    for block in data.get("content", []):
        if block.get("type") == "text":
            text = block.get("text", "")
            break

    # Strip markdown fences if present
    clean = text.replace("```json", "").replace("```", "").strip()

    try:
        result = json.loads(clean)
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="Claude returned non-JSON response")

    return result


@app.get("/health")
async def health():
    return {"status": "ok"}
