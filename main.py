"""
Capital.com API Proxy – Hardened 1.2 (hard‑coded credentials)
Autor: Júlio / ChatGPT
Data: 2025‑05‑16

⚠️  As credenciais estão hard‑coded conforme solicitado.
     Proteja este arquivo e o repositório privado.
"""
from __future__ import annotations

import time, asyncio
from typing import Optional, List, Dict, Any

import httpx
from fastapi import FastAPI, HTTPException, Body, Query, status
from pydantic import BaseModel, Field

###############################################################################
# Credenciais e Configuração (HARD‑CODED)
###############################################################################
API_KEY      = "Xkd7V5X79oXWjBjn"
API_EMAIL    = "juliocesarklamt@outlook.com"
API_PASSWORD = "99156617aA**"
BASE_URL     = "https://demo-api-capital.backend-capital.com/api/v1"
TIMEOUT_S    = 10
RATE_LIMIT   = 25  # demo: 30 req/min

###############################################################################
# Tokens & controle de sessão
###############################################################################
SESSION_TOKEN: Optional[str] = None
SECURITY_TOKEN: Optional[str] = None
TOKEN_EXPIRES_AT: float = 0
_sema = asyncio.Semaphore(RATE_LIMIT)

###############################################################################
# Modelos Pydantic – principais
###############################################################################
class SwitchAccountRequest(BaseModel):
    accountId: str

class CreatePositionRequest(BaseModel):
    epic: str
    direction: str
    size: float
    leverage: float
    guaranteedStop: bool = False
    trailingStop: bool = False
    stopLevel: Optional[float] = None
    stopDistance: Optional[float] = None
    stopAmount: Optional[float] = None
    profitLevel: Optional[float] = None
    profitDistance: Optional[float] = None
    profitAmount: Optional[float] = None

class UpdatePositionRequest(CreatePositionRequest):
    epic: Optional[str] = None
    direction: Optional[str] = None
    size: Optional[float] = None
    leverage: Optional[float] = None

class CreateWorkingOrderRequest(BaseModel):
    direction: str
    epic: str
    size: float
    level: float
    type: str
    goodTillDate: Optional[str] = None
    guaranteedStop: bool = False
    trailingStop: bool = False
    stopLevel: Optional[float] = None
    stopDistance: Optional[float] = None
    stopAmount: Optional[float] = None
    profitLevel: Optional[float] = None
    profitDistance: Optional[float] = None
    profitAmount: Optional[float] = None

class UpdateWorkingOrderRequest(CreateWorkingOrderRequest):
    direction: Optional[str] = None
    size: Optional[float] = None
    level: Optional[float] = None
    type: Optional[str] = None

class CreateWatchlistRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=20)
    epics: Optional[List[str]] = None

###############################################################################
# Funções auxiliares
###############################################################################

def _auth_headers() -> Dict[str, str]:
    return {
        "X-CAP-API-KEY": API_KEY,
        "CST": SESSION_TOKEN or "",
        "X-SECURITY-TOKEN": SECURITY_TOKEN or "",
    }

async def _login() -> None:
    """Autentica e armazena tokens/expiração (15 min)"""
    global SESSION_TOKEN, SECURITY_TOKEN, TOKEN_EXPIRES_AT
    async with httpx.AsyncClient(timeout=TIMEOUT_S) as c:
        r = await c.post(f"{BASE_URL}/session", json={"identifier": API_EMAIL, "password": API_PASSWORD}, headers={"X-CAP-API-KEY": API_KEY})
    if r.status_code != 200:
        raise HTTPException(r.status_code, f"Falha login: {r.text}")
    SESSION_TOKEN   = r.headers.get("CST")
    SECURITY_TOKEN  = r.headers.get("X-SECURITY-TOKEN")
    TOKEN_EXPIRES_AT = time.time() + 14 * 60   # buffer

async def _ensure_session() -> None:
    if not SESSION_TOKEN or time.time() >= TOKEN_EXPIRES_AT:
        await _login()

async def _request(method: str, endpoint: str, *, json: Any = None, params: Dict[str, Any] | None = None, retry: bool = True):
    await _ensure_session()
    async with _sema:
        async with httpx.AsyncClient(timeout=TIMEOUT_S, headers=_auth_headers()) as c:
            r = await c.request(method, f"{BASE_URL}{endpoint}", json=json, params=params)
    if r.status_code == 401 and retry:
        await _login()
        return await _request(method, endpoint, json=json, params=params, retry=False)
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text)
    return r.json() if r.text else {}

###############################################################################
# FastAPI App
###############################################################################
app = FastAPI(title="Capital.com API Proxy – Hardened (Hard‑coded)")

@app.on_event("startup")
async def _startup():
    await _login()

# Sessão
@app.post("/proxy/login")
async def proxy_login():
    await _login()
    return {"message": "Sessão renovada"}

@app.get("/proxy/ping")
async def ping():
    return await _request("GET", "/ping")

@app.get("/proxy/session")
async def session_details():
    return await _request("GET", "/session")

@app.put("/proxy/session")
async def session_switch(req: SwitchAccountRequest):
    return await _request("PUT", "/session", json=req.dict())

@app.delete("/proxy/session")
async def session_logout():
    await _request("DELETE", "/session")
    globals().update(SESSION_TOKEN=None, SECURITY_TOKEN=None, TOKEN_EXPIRES_AT=0)
    return {"message": "Sessão encerrada"}

# Conta
@app.get("/proxy/account")
async def account_list():
    return await _request("GET", "/accounts")

@app.get("/proxy/account/preferences")
async def account_prefs():
    return await _request("GET", "/accounts/preferences")

@app.put("/proxy/account/preferences")
async def update_account_prefs(payload: Dict[str, Any] = Body(...)):
    body = {k: v for k, v in payload.items() if k in {"leverages", "hedgingMode"}}
    if not body:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Informe 'leverages' e/ou 'hedgingMode'.")
    return await _request("PUT", "/accounts/preferences", json=body)

# Posições
@app.get("/proxy/positions")
async def positions_open():
    return await _request("GET", "/positions")

@app.post("/proxy/position")
async def position_create(req: CreatePositionRequest):
    return await _request("POST", "/positions", json=req.dict())

@app.put("/proxy/position/{deal_id}")
async def position_update(deal_id: str, req: UpdatePositionRequest):
    return await _request("PUT", f"/positions/{deal_id}", json=req.dict(exclude_none=True))

@app.delete("/proxy/position/{deal_id}")
async def position_close(deal_id: str):
    return await _request("DELETE", f"/positions/{deal_id}")

# Ordens
@app.get("/proxy/orders")
async def orders_open():
    return await _request("GET", "/workingorders")

@app.post("/proxy/order")
async def order_create(req: CreateWorkingOrderRequest):
    return await _request("POST", "/workingorders", json=req.dict())

@app.put("/proxy/order/{deal_id}")
async def order_update(deal_id: str, req: UpdateWorkingOrderRequest):
    return await _request("PUT", f"/workingorders/{deal_id}", json=req.dict(exclude_none=True))

@app.delete("/proxy/order/{deal_id}")
async def order_delete(deal_id: str):
    return await _request("DELETE", f"/workingorders/{deal_id}")

# Mercados
@app.get("/proxy/markets")
async def markets_list(searchTerm: Optional[str] = None, epics: Optional[str] = None):
    return await _request("GET", "/markets", params={k: v for k, v in {"searchTerm": searchTerm, "epics": epics}.items() if v})

@app.get("/proxy/market/{epic}")
async def market_get(epic: str):
    return
