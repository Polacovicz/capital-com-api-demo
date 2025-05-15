from fastapi import FastAPI, Body, Query, HTTPException
import httpx, asyncio
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

app = FastAPI(title="Capital.com API Proxy")

API_KEY = "Xkd7V5X79oXWjBjn"
API_EMAIL = "juliocesarklamt@outlook.com"
API_PASSWORD = "99156617aA**"
BASE_URL = "https://demo-api-capital.backend-capital.com/api/v1"

SESSION_TOKEN: Optional[str] = None
SECURITY_TOKEN: Optional[str] = None

# 🔹 Models de Sessão e Conta
class SessionRequest(BaseModel):
    identifier: str
    password: str
    encryptedPassword: Optional[bool] = False

class SwitchAccountRequest(BaseModel):
    accountId: str

# 🔹 Models de Posições, Ordens e Watchlists
class CreatePositionRequest(BaseModel):
    epic: str
    direction: str
    size: float
    leverage: float
    guaranteedStop: Optional[bool] = False
    trailingStop: Optional[bool] = False
    stopLevel: Optional[float] = None
    stopDistance: Optional[float] = None
    stopAmount: Optional[float] = None
    profitLevel: Optional[float] = None
    profitDistance: Optional[float] = None
    profitAmount: Optional[float] = None

class UpdatePositionRequest(BaseModel):
    leverage: Optional[float] = None
    guaranteedStop: Optional[bool] = None
    trailingStop: Optional[bool] = None
    stopLevel: Optional[float] = None
    stopDistance: Optional[float] = None
    stopAmount: Optional[float] = None
    profitLevel: Optional[float] = None
    profitDistance: Optional[float] = None
    profitAmount: Optional[float] = None

class CreateWorkingOrderRequest(BaseModel):
    direction: str
    epic: str
    size: float
    level: float
    type: str
    goodTillDate: Optional[str] = None
    guaranteedStop: Optional[bool] = False
    trailingStop: Optional[bool] = False
    stopLevel: Optional[float] = None
    stopDistance: Optional[float] = None
    stopAmount: Optional[float] = None
    profitLevel: Optional[float] = None
    profitDistance: Optional[float] = None
    profitAmount: Optional[float] = None

class UpdateWorkingOrderRequest(BaseModel):
    level: Optional[float] = None
    goodTillDate: Optional[str] = None
    guaranteedStop: Optional[bool] = None
    trailingStop: Optional[bool] = None
    stopLevel: Optional[float] = None
    stopDistance: Optional[float] = None
    stopAmount: Optional[float] = None
    profitLevel: Optional[float] = None
    profitDistance: Optional[float] = None
    profitAmount: Optional[float] = None

class CreateWatchlistRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=20)
    epics: Optional[List[str]] = None

# 🔹 Utilitários de Sessão
async def login():
    global SESSION_TOKEN, SECURITY_TOKEN
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{BASE_URL}/session",
            json={"identifier": API_EMAIL, "password": API_PASSWORD},
            headers={"X-CAP-API-KEY": API_KEY},
        )
    if r.status_code == 200:
        SESSION_TOKEN = r.headers.get("CST")
        SECURITY_TOKEN = r.headers.get("X-SECURITY-TOKEN")
    else:
        raise RuntimeError(f"Falha no login: {r.text}")

async def ensure_session():
    if SESSION_TOKEN is None:
        await login()

async def make_request(method: str, endpoint: str, data: Any = None, params: Dict[str,Any] = None):
    await ensure_session()
    headers = {
        "X-CAP-API-KEY": API_KEY,
        "CST": SESSION_TOKEN or "",
        "X-SECURITY-TOKEN": SECURITY_TOKEN or "",
    }
    async with httpx.AsyncClient() as client:
        r = await client.request(method, BASE_URL + endpoint, json=data, params=params, headers=headers)
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text)
    return r.json() if r.text else {}

@app.on_event("startup")
async def startup():
    asyncio.create_task(login())

# 🔹 Sessão
@app.post("/proxy/login")
async def proxy_login():
    await login()
    return {"message": "Sessão renovada"}

@app.get("/proxy/ping")
async def ping():
    return await make_request("GET", "/ping")

@app.get("/proxy/session")
async def session_details():
    return await make_request("GET", "/session")

@app.post("/proxy/session")
async def session_create(req: SessionRequest):
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{BASE_URL}/session", json=req.dict(), headers={"X-CAP-API-KEY": API_KEY})
    if r.status_code == 200:
        global SESSION_TOKEN, SECURITY_TOKEN
        SESSION_TOKEN = r.headers.get("CST")
        SECURITY_TOKEN = r.headers.get("X-SECURITY-TOKEN")
        return r.json()
    raise HTTPException(r.status_code, r.text)

@app.put("/proxy/session")
async def session_switch(req: SwitchAccountRequest):
    return await make_request("PUT", "/session", data=req.dict())

@app.delete("/proxy/session")
async def session_logout():
    await make_request("DELETE", "/session")
    global SESSION_TOKEN, SECURITY_TOKEN
    SESSION_TOKEN = SECURITY_TOKEN = None
    return {"message": "Sessão encerrada"}

# 🔹 Conta
@app.get("/proxy/account")
async def account_list():
    return await make_request("GET", "/accounts")

@app.get("/proxy/account/preferences")
async def account_prefs():
    return await make_request("GET", "/accounts/preferences")

@app.put("/proxy/account/preferences")
async def update_account_prefs(
    payload: Dict[str, Any] = Body(...)
):
    """
    Atualiza alavancagem e/ou hedging.
    Aceita somente JSON no corpo com 'leverages' e/ou 'hedgingMode'.
    """
    leverages = payload.get("leverages")
    hedging_mode = payload.get("hedgingMode")

    if leverages is None and hedging_mode is None:
        raise HTTPException(
            status_code=400,
            detail="É necessário informar 'leverages' e/ou 'hedgingMode'."
        )

    body: Dict[str, Any] = {}
    if leverages is not None:
        body["leverages"] = leverages
    if hedging_mode is not None:
        body["hedgingMode"] = hedging_mode

    return await make_request("PUT", "/accounts/preferences", data=body)

# 🔹 Histórico
@app.get("/proxy/history/activity")
async def history_activity(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    last_period: Optional[int] = Query(None, alias="lastPeriod"),
    detailed: Optional[bool] = Query(False),
    deal_id: Optional[str] = Query(None, alias="dealId"),
    filter_str: Optional[str] = Query(None, alias="filter")
):
    params = {k: v for k, v in {
        "from": from_date, "to": to_date, "lastPeriod": last_period,
        "detailed": detailed or None, "dealId": deal_id, "filter": filter_str
    }.items() if v is not None}
    return await make_request("GET", "/history/activity", params=params)

@app.get("/proxy/history/transactions")
async def history_transactions(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    last_period: Optional[int] = Query(None, alias="lastPeriod"),
    tx_type: Optional[str] = Query(None, alias="type")
):
    params = {k: v for k, v in {
        "from": from_date, "to": to_date, "lastPeriod": last_period, "type": tx_type
    }.items() if v is not None}
    return await make_request("GET", "/history/transactions", params=params)

# 🔹 Confirmação
@app.get("/proxy/confirms/{deal_reference}")
async def confirm(deal_reference: str):
    return await make_request("GET", f"/confirms/{deal_reference}")

# 🔹 Posições
@app.get("/proxy/positions")
async def positions_open():
    return await make_request("GET", "/positions")

@app.post("/proxy/position")
async def position_create(req: CreatePositionRequest):
    return await make_request("POST", "/positions", data=req.dict())

@app.get("/proxy/position/{deal_id}")
async def position_get(deal_id: str):
    return await make_request("GET", f"/positions/{deal_id}")

@app.put("/proxy/position/{deal_id}")
async def position_update(deal_id: str, req: UpdatePositionRequest):
    return await make_request("PUT", f"/positions/{deal_id}", data=req.dict(exclude_none=True))

@app.delete("/proxy/position/{deal_id}")
async def position_close(deal_id: str):
    return await make_request("DELETE", f"/positions/{deal_id}")

# 🔹 Ordens
@app.get("/proxy/orders")
async def orders_open():
    return await make_request("GET", "/workingorders")

@app.post("/proxy/order")
async def order_create(req: CreateWorkingOrderRequest):
    return await make_request("POST", "/workingorders", data=req.dict())

@app.put("/proxy/order/{deal_id}")
async def order_update(deal_id: str, req: UpdateWorkingOrderRequest):
    return await make_request("PUT", f"/workingorders/{deal_id}", data=req.dict(exclude_none=True))

@app.delete("/proxy/order/{deal_id}")
async def order_delete(deal_id: str):
    return await make_request("DELETE", f"/workingorders/{deal_id}")

# 🔹 Mercados
@app.get("/proxy/markets")
async def markets_list(
    searchTerm: Optional[str] = Query(None),
    epics: Optional[str] = Query(None)
):
    params: Dict[str,Any] = {}
    if searchTerm: params["searchTerm"] = searchTerm
    if epics:      params["epics"]      = epics
    return await make_request("GET", "/markets", params=params)

@app.get("/proxy/markets/navigation")
async def market_categories():
    return await make_request("GET", "/markets/navigation")

@app.get("/proxy/markets/navigation/{node_id}")
async def market_subnodes(
    node_id: str,
    limit: Optional[int] = Query(500, le=500)
):
    return await make_request("GET", f"/markets/navigation/{node_id}", params={"limit": limit})

@app.get("/proxy/market/{epic}")
async def market_get(epic: str):
    return await make_request("GET", f"/markets/{epic}")

# 🔹 Preços
@app.get("/proxy/prices/{epic}")
async def prices_historical(
    epic: str,
    resolution: Optional[str] = Query("MINUTE"),
    max_entries: Optional[int] = Query(10, alias="max_entries", le=1000),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to")
):
    params: Dict[str,Any] = {"resolution": resolution, "max_entries": max_entries}
    if from_date: params["from"] = from_date
    if to_date:   params["to"]   = to_date
    return await make_request("GET", f"/prices/{epic}", params=params)

# 🔹 Sentimento
@app.get("/proxy/sentiment/{market_id}")
async def sentiment_get(market_id: str):
    return await make_request("GET", f"/sentiment/{market_id}")

# 🔹 Watchlists
@app.get("/proxy/watchlists")
async def watchlists_all():
    return await make_request("GET", "/watchlists")

@app.post("/proxy/watchlist")
async def watchlist_create(req: CreateWatchlistRequest):
    return await make_request("POST", "/watchlists", data=req.dict())

@app.get("/proxy/watchlist/{watchlist_id}")
async def watchlist_get(watchlist_id: str):
    return await make_request("GET", f"/watchlists/{watchlist_id}")

@app.delete("/proxy/watchlist/{watchlist_id}")
async def watchlist_delete(watchlist_id: str):
    return await make_request("DELETE", f"/watchlists/{watchlist_id}")
