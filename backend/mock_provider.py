from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel
from typing import Optional, Dict, Any
import asyncio
import json

app = FastAPI(title="Mock Payment Provider", version="1.1.0")

# In-memory provider state
provider_state = {
    "schema_mode": "original",  # "original" (price) or "changed" (amount)
    "simulate_failure": False,
    "failure_status_code": 500,
    "delay_seconds": 0.0,
    "invalid_json": False
}

class PaymentPayload(BaseModel):
    amount_or_price: Optional[float] = None
    currency: Optional[str] = "USD"
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "mock_payment_provider",
        "schema_mode": provider_state["schema_mode"],
        "port": 8001
    }

@app.post("/admin/schema-mode")
async def set_schema_mode(mode: str):
    if mode not in ["original", "changed"]:
        raise HTTPException(status_code=400, detail="Mode must be 'original' or 'changed'")
    provider_state["schema_mode"] = mode
    return {"message": f"Schema mode updated to {mode}", "schema_mode": mode}

@app.post("/admin/simulate-failure")
async def toggle_failure(enable: bool, status_code: int = 500):
    provider_state["simulate_failure"] = enable
    provider_state["failure_status_code"] = status_code
    return {"simulate_failure": enable, "status_code": status_code}

@app.post("/admin/simulate-delay")
async def toggle_delay(seconds: float = 0.0):
    provider_state["delay_seconds"] = seconds
    return {"delay_seconds": seconds}

@app.post("/admin/simulate-invalid-json")
async def toggle_invalid_json(enable: bool):
    provider_state["invalid_json"] = enable
    return {"invalid_json": enable}

@app.api_route("/payments/echo", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def echo_request(request: Request):
    """Echoes method, headers, query params and body for proxy validation"""
    if provider_state["delay_seconds"] > 0:
        await asyncio.sleep(provider_state["delay_seconds"])
        
    if provider_state["simulate_failure"]:
        raise HTTPException(
            status_code=provider_state["failure_status_code"],
            detail="Mock payment provider simulated upstream error"
        )
        
    if provider_state["invalid_json"]:
        return Response(content="{malformed_json: missing_quotes,", media_type="application/json")
        
    body_bytes = await request.body()
    body_text = body_bytes.decode("utf-8") if body_bytes else ""
    try:
        body_json = json.loads(body_text) if body_text else None
    except Exception:
        body_json = None

    return {
        "method": request.method,
        "query_params": dict(request.query_params),
        "headers": {k: v for k, v in request.headers.items() if k.lower().startswith("x-") or k.lower() in ["authorization", "content-type"]},
        "body_json": body_json,
        "body_raw": body_text
    }

@app.api_route("/payments/{payment_id}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def handle_payment(payment_id: str, request: Request):
    if provider_state["delay_seconds"] > 0:
        await asyncio.sleep(provider_state["delay_seconds"])

    if provider_state["simulate_failure"]:
        raise HTTPException(
            status_code=provider_state["failure_status_code"],
            detail="Mock payment provider simulated upstream error"
        )

    if provider_state["invalid_json"]:
        return Response(content="{invalid_json_payload: [unclosed", media_type="application/json")

    mode = request.query_params.get("mode", provider_state["schema_mode"])
    
    if mode == "changed":
        # Changed schema: 'amount' replaces 'price'
        return {
            "payment_id": payment_id,
            "amount": 500,
            "status": "success",
            "currency": "USD",
            "method_received": request.method
        }
    else:
        # Original schema: 'price'
        return {
            "payment_id": payment_id,
            "price": 500,
            "status": "success",
            "currency": "USD",
            "method_received": request.method
        }

@app.api_route("/payments", methods=["GET", "POST"])
async def payments_collection(request: Request):
    if provider_state["delay_seconds"] > 0:
        await asyncio.sleep(provider_state["delay_seconds"])

    if provider_state["simulate_failure"]:
        raise HTTPException(
            status_code=provider_state["failure_status_code"],
            detail="Mock payment provider simulated upstream error"
        )

    mode = request.query_params.get("mode", provider_state["schema_mode"])
    if mode == "changed":
        return {
            "payment_id": "P101",
            "amount": 500,
            "status": "success"
        }
    return {
        "payment_id": "P101",
        "price": 500,
        "status": "success"
    }

@app.get("/status/{code}")
async def return_status_code(code: int):
    """Returns exact status code for proxy status forwarding testing"""
    if code >= 400:
        raise HTTPException(status_code=code, detail=f"Custom upstream error code {code}")
    return {"status_code": code, "status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("mock_provider:app", host="127.0.0.1", port=8001, reload=False)
