from fastapi import FastAPI, Body, Query, Path, HTTPException
import httpx, asyncio
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from enum import Enum
from datetime import datetime

app = FastAPI(title="Capital.com API Proxy")

# 🔹 Credenciais da API da Capital.com
API_KEY = "Xkd7V5X79oXWjBjn"  # Substitua pela sua chave da API
API_EMAIL = "juliocesarklamt@outlook.com"  # Substitua pelo e-mail da API
API_PASSWORD = "99156617aA**"  # Substitua pela senha da API
BASE_URL = "https://demo-api-capital.backend-capital.com/api/v1"

# 🔹 Tokens de sessão
SESSION_TOKEN = None
SECURITY_TOKEN = None

# 🔹 Modelos de dados
class CreatePositionRequest(BaseModel):
    epic: str
    direction: str  # "BUY" ou "SELL"
    size: float
    guaranteedStop: Optional[bool] = False
    trailingStop: Optional[bool] = False
    stopLevel: Optional[float] = None
    stopDistance: Optional[float] = None
    stopAmount: Optional[float] = None
    profitLevel: Optional[float] = None
    profitDistance: Optional[float] = None
    profitAmount: Optional[float] = None

class UpdatePositionRequest(BaseModel):
    guaranteedStop: Optional[bool] = None
    trailingStop: Optional[bool] = None
    stopLevel: Optional[float] = None
    stopDistance: Optional[float] = None
    stopAmount: Optional[float] = None
    profitLevel: Optional[float] = None
    profitDistance: Optional[float] = None
    profitAmount: Optional[float] = None

class CreateWorkingOrderRequest(BaseModel):
    direction: str  # "BUY" ou "SELL"
    epic: str
    size: float
    level: float
    type: str  # "LIMIT" ou "STOP"
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

class UpdateAccountPreferencesRequest(BaseModel):
    leverages: Optional[Dict[str, int]] = None
    hedgingMode: Optional[bool] = None

class CreateWatchlistRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=20)
    epics: Optional[List[str]] = None

class AddMarketToWatchlistRequest(BaseModel):
    epic: str

class SessionRequest(BaseModel):
    identifier: str
    password: str
    encryptedPassword: Optional[bool] = False

class SwitchAccountRequest(BaseModel):
    accountId: str

# 🔹 Funções de utilidade
async def login():
    """Autentica na API da Capital.com e armazena os tokens de sessão."""
    global SESSION_TOKEN, SECURITY_TOKEN
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/session",
            json={"identifier": API_EMAIL, "password": API_PASSWORD},
            headers={"X-CAP-API-KEY": API_KEY},
        )
        if response.status_code == 200:
            SESSION_TOKEN = response.headers.get("CST")
            SECURITY_TOKEN = response.headers.get("X-SECURITY-TOKEN")
            print("🔄 Token de sessão atualizado:", SESSION_TOKEN)
        else:
            print("⚠️ Erro ao fazer login:", response.text)

async def ensure_valid_session():
    if SESSION_TOKEN is None:
        print("⚠️ Token ausente! Fazendo login novamente...")
        await login()

async def keep_session_alive():
    while True:
        await login()
        await asyncio.sleep(8 * 60)  # Renova a cada 8 minutos

async def make_request(method: str, endpoint: str, data=None, params=None):
    await ensure_valid_session()
    url = f"{BASE_URL}{endpoint}"
    headers = {
        "X-CAP-API-KEY": API_KEY,
        "CST": SESSION_TOKEN or "",
        "X-SECURITY-TOKEN": SECURITY_TOKEN or "",
    }
    print(f"📌 Enviando requisição: {method} {url}")
    print(f"📌 Headers: {headers}")
    print(f"📌 Dados: {data}")
    print(f"📌 Parâmetros: {params}")
    
    async with httpx.AsyncClient() as client:
        response = await client.request(method, url, json=data, params=params, headers=headers)
        print(f"📌 Resposta: {response.status_code} - {response.text}")
        
        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=response.text)
            
        return response.json() if response.text else {"status": "success"}

# 🔹 Inicialização
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(keep_session_alive())

# 🔹 Endpoints Gerais
@app.get("/proxy/time")
async def get_server_time():
    """Retorna o horário do servidor da API."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/time")
        return response.json()

@app.get("/proxy/ping")
async def ping_service():
    """Mantém a sessão viva."""
    return await make_request("GET", "/ping")

# 🔹 Endpoints de Sessão
@app.post("/proxy/login")
async def proxy_login():
    await login()
    return {"message": "Sessão renovada", "session": SESSION_TOKEN}

@app.get("/proxy/session/encryption-key")
async def get_encryption_key():
    """Obtém a chave de criptografia para autenticação segura."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/session/encryptionKey",
            headers={"X-CAP-API-KEY": API_KEY}
        )
        return response.json()

@app.get("/proxy/session")
async def get_session_details():
    """Retorna os detalhes da sessão atual."""
    return await make_request("GET", "/session")

@app.post("/proxy/session/create")
async def create_session(request: SessionRequest):
    """Cria uma nova sessão com a API."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/session",
            json=request.dict(),
            headers={"X-CAP-API-KEY": API_KEY}
        )
        if response.status_code == 200:
            global SESSION_TOKEN, SECURITY_TOKEN
            SESSION_TOKEN = response.headers.get("CST")
            SECURITY_TOKEN = response.headers.get("X-SECURITY-TOKEN")
            return response.json()
        else:
            raise HTTPException(status_code=response.status_code, detail=response.text)

@app.put("/proxy/session")
async def switch_active_account(request: SwitchAccountRequest):
    """Altera a conta ativa para operações."""
    return await make_request("PUT", "/session", request.dict())

@app.delete("/proxy/session")
async def logout():
    """Encerra a sessão atual."""
    response = await make_request("DELETE", "/session")
    global SESSION_TOKEN, SECURITY_TOKEN
    SESSION_TOKEN = None
    SECURITY_TOKEN = None
    return response

# 🔹 Endpoints de Contas
@app.get("/proxy/account")
async def get_account_details():
    """Retorna os detalhes de todas as contas do usuário."""
    return await make_request("GET", "/accounts")

@app.get("/proxy/account/preferences")
async def get_account_preferences():
    """Retorna as preferências da conta atual."""
    return await make_request("GET", "/accounts/preferences")

@app.put("/proxy/account/preferences")
async def update_account_preferences(preferences: UpdateAccountPreferencesRequest):
    """Atualiza as preferências da conta atual."""
    return await make_request("PUT", "/accounts/preferences", preferences.dict())

@app.get("/proxy/history/activity")
async def get_account_activity(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    last_period: Optional[int] = Query(None, alias="lastPeriod"),
    detailed: Optional[bool] = Query(False),
    deal_id: Optional[str] = Query(None, alias="dealId"),
    filter_str: Optional[str] = Query(None, alias="filter")
):
    """Retorna o histórico de atividades da conta."""
    params = {}
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date
    if last_period:
        params["lastPeriod"] = last_period
    if detailed:
        params["detailed"] = detailed
    if deal_id:
        params["dealId"] = deal_id
    if filter_str:
        params["filter"] = filter_str
        
    return await make_request("GET", "/history/activity", params=params)

@app.get("/proxy/history/transactions")
async def get_account_transactions(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    last_period: Optional[int] = Query(None, alias="lastPeriod"),
    type: Optional[str] = None
):
    """Retorna o histórico de transações da conta."""
    params = {}
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date
    if last_period:
        params["lastPeriod"] = last_period
    if type:
        params["type"] = type
        
    return await make_request("GET", "/history/transactions", params=params)

@app.post("/proxy/account/topup")
async def adjust_demo_balance(amount: float = Body(..., embed=True)):
    """Ajusta o saldo da conta demo."""
    return await make_request("POST", "/accounts/topUp", {"amount": amount})

# 🔹 Endpoints de Confirmação
@app.get("/proxy/confirms/{deal_reference}")
async def get_position_confirmation(deal_reference: str):
    """Retorna a confirmação de uma negociação pelo seu ID de referência."""
    return await make_request("GET", f"/confirms/{deal_reference}")

# 🔹 Endpoints de Posições
@app.get("/proxy/positions")
async def get_open_positions():
    """Retorna todas as posições abertas da conta ativa."""
    return await make_request("GET", "/positions")

@app.post("/proxy/position")
async def create_position(position: CreatePositionRequest = Body(...)):
    """Abre uma nova posição utilizando o endpoint /positions."""
    print("📌 Enviando posição com dados:", position.dict())
    return await make_request("POST", "/positions", position.dict())

@app.get("/proxy/position/{deal_id}")
async def get_position(deal_id: str):
    """Retorna os detalhes de uma posição específica."""
    return await make_request("GET", f"/positions/{deal_id}")

@app.put("/proxy/position/{deal_id}")
async def update_position(deal_id: str, update_data: UpdatePositionRequest):
    """Atualiza uma posição existente."""
    return await make_request("PUT", f"/positions/{deal_id}", update_data.dict())

@app.delete("/proxy/position/{deal_id}")
async def close_position(deal_id: str):
    """Fecha uma posição aberta."""
    return await make_request("DELETE", f"/positions/{deal_id}")

# 🔹 Endpoints de Ordens
@app.get("/proxy/orders")
async def get_working_orders():
    """Retorna todas as ordens pendentes da conta ativa."""
    return await make_request("GET", "/workingorders")

@app.post("/proxy/order")
async def create_working_order(order: CreateWorkingOrderRequest):
    """Cria uma nova ordem pendente."""
    return await make_request("POST", "/workingorders", order.dict())

@app.put("/proxy/order/{deal_id}")
async def update_working_order(deal_id: str, update_data: UpdateWorkingOrderRequest):
    """Atualiza uma ordem pendente existente."""
    return await make_request("PUT", f"/workingorders/{deal_id}", update_data.dict())

@app.delete("/proxy/order/{deal_id}")
async def delete_working_order(deal_id: str):
    """Remove uma ordem pendente."""
    return await make_request("DELETE", f"/workingorders/{deal_id}")

# 🔹 Endpoints de Mercados
@app.get("/proxy/markets/navigation")
async def get_market_categories():
    """Retorna todas as categorias de mercado de alto nível."""
    return await make_request("GET", "/marketnavigation")

@app.get("/proxy/markets/navigation/{node_id}")
async def get_market_category_subnodes(
    node_id: str, 
    limit: Optional[int] = Query(500, le=500)
):
    """Retorna todos os sub-nós de uma categoria de mercado."""
    params = {"limit": limit}
    return await make_request("GET", f"/marketnavigation/{node_id}", params=params)

@app.get("/proxy/markets")
async def get_markets_details(
    search_term: Optional[str] = Query(None, alias="searchTerm"),
    epics: Optional[str] = Query(None)
):
    """Retorna os detalhes de múltiplos mercados."""
    params = {}
    if search_term:
        params["searchTerm"] = search_term
    elif epics:
        params["epics"] = epics
        
    return await make_request("GET", "/markets", params=params)

@app.get("/proxy/market/{epic}")
async def get_market_details(epic: str):
    """Retorna os detalhes de um mercado específico."""
    return await make_request("GET", f"/markets/{epic}")

# 🔹 Endpoints de Preços
@app.get("/proxy/prices/{epic}")
async def get_historical_prices(
    epic: str, 
    resolution: Optional[str] = Query("MINUTE"),
    max_entries: Optional[int] = Query(10, alias="max", le=1000),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to")
):
    """Retorna os preços históricos de um instrumento."""
    params = {"resolution": resolution, "max": max_entries}
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date
        
    return await make_request("GET", f"/prices/{epic}", params=params)

# 🔹 Endpoints de Sentimento do Cliente
@app.get("/proxy/sentiment")
async def get_client_sentiment_multiple(market_ids: str = Query(..., alias="marketIds")):
    """Retorna o sentimento do cliente para múltiplos mercados."""
    params = {"marketIds": market_ids}
    return await make_request("GET", "/clientsentiment", params=params)

@app.get("/proxy/sentiment/{market_id}")
async def get_client_sentiment(market_id: str):
    """Retorna o sentimento do cliente para um mercado específico."""
    return await make_request("GET", f"/clientsentiment/{market_id}")

# 🔹 Endpoints de Listas de Observação
@app.get("/proxy/watchlists")
async def get_all_watchlists():
    """Retorna todas as listas de observação do usuário."""
    return await make_request("GET", "/watchlists")

@app.post("/proxy/watchlist")
async def create_watchlist(watchlist: CreateWatchlistRequest):
    """Cria uma nova lista de observação."""
    return await make_request("POST", "/watchlists", watchlist.dict())

@app.get("/proxy/watchlist/{watchlist_id}")
async def get_watchlist(watchlist_id: str):
    """Retorna os detalhes de uma lista de observação específica."""
    return await make_request("GET", f"/watchlists/{watchlist_id}")

@app.put("/proxy/watchlist/{watchlist_id}")
async def add_market_to_watchlist(watchlist_id: str, market: AddMarketToWatchlistRequest):
    """Adiciona um mercado a uma lista de observação."""
    return await make_request("PUT", f"/watchlists/{watchlist_id}", market.dict())

@app.delete("/proxy/watchlist/{watchlist_id}")
async def delete_watchlist(watchlist_id: str):
    """Remove uma lista de observação."""
    return await make_request("DELETE", f"/watchlists/{watchlist_id}")

@app.delete("/proxy/watchlist/{watchlist_id}/{epic}")
async def remove_market_from_watchlist(watchlist_id: str, epic: str):
    """Remove um mercado de uma lista de observação."""
    return await make_request("DELETE", f"/watchlists/{watchlist_id}/{epic}")
