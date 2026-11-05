import sys
import os

# Ensure backend directory is in sys.path so modules can import config, database, etc. regardless of cwd
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from fastapi import FastAPI, Request, Response, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import httpx
import json
import logging
import time
import uuid
import secrets
import hashlib
from typing import Optional, Dict, Any, List

from config import settings
from security import is_safe_target_url, sanitize_headers
from database import (
    init_db,
    get_connection,
    create_project,
    get_project,
    get_project_by_api_key,
    save_endpoint_schema,
    get_latest_schema,
    get_baseline_schema,
    save_schema_change,
    upsert_mapping,
    get_approved_mappings,
    get_mappings_for_project,
    log_transformation,
    record_extension_download,
    get_download_stats,
    DB_PATH
)
from schema_detector import extract_schema, compare_schemas, compute_schema_hash
from mapping_engine import IntelligentMappingEngine
from mapping_service import (
    approve_mapping_request,
    reject_mapping_request,
    disable_mapping_request
)
from transformer import transform_response
from auth import (
    hash_password,
    verify_password,
    create_session_token,
    get_current_user,
    require_admin
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("shim.proxy")

# Initialize SQLite tables on startup
init_db()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Adaptive API Compatibility Proxy"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

mapping_engine = IntelligentMappingEngine(fallback_mode=True)

# File paths in frontend/
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
LANDING_PAGE_PATH = os.path.join(FRONTEND_DIR, "index.html")
CONSOLE_PAGE_PATH = os.path.join(FRONTEND_DIR, "console.html")
VSIX_PATH = os.path.join(FRONTEND_DIR, "public", "shim-vscode-extension.vsix")

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    role: Optional[str] = "customer"

class LoginRequest(BaseModel):
    username_or_email: str
    password: str

class CreateProjectRequest(BaseModel):
    name: str

class CreateIntegrationRequest(BaseModel):
    name: str
    target_base_url: str
    auth_token: Optional[str] = None

def ensure_default_project():
    conn = get_connection()
    with conn:
        admin_user = conn.execute("SELECT * FROM users WHERE username = 'admin'").fetchone()
        if not admin_user:
            admin_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO users (id, username, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (admin_id, "admin", "admin@shim.dev", hash_password("admin123"), "admin", time.time())
            )
        else:
            admin_id = admin_user["id"]

        default_proj = conn.execute("SELECT * FROM projects WHERE id = 'default_project'").fetchone()
        if not default_proj:
            conn.execute(
                "INSERT INTO projects (id, name, owner_id, api_key, created_at) VALUES (?, ?, ?, ?, ?)",
                ("default_project", "Universal API Gateway", admin_id, "shim_live_default_key", time.time())
            )

ensure_default_project()

# --- Serve Public Landing Page ---
@app.get("/", include_in_schema=False)
@app.get("/app", include_in_schema=False)
async def serve_landing_page():
    if os.path.exists(LANDING_PAGE_PATH):
        return FileResponse(LANDING_PAGE_PATH)
    return {"message": "SHIM Landing Page"}

# --- Serve Developer Console ---
@app.get("/console", include_in_schema=False)
@app.get("/admin", include_in_schema=False)
@app.get("/dashboard", include_in_schema=False)
async def serve_developer_console():
    if os.path.exists(CONSOLE_PAGE_PATH):
        return FileResponse(CONSOLE_PAGE_PATH)
    elif os.path.exists(LANDING_PAGE_PATH):
        return FileResponse(LANDING_PAGE_PATH)
    return {"message": "SHIM Developer Console"}

# --- Anonymous Extension Download & Tracking Endpoints ---
@app.get("/download/shim-vscode-extension.vsix", include_in_schema=False)
@app.get("/api/download/extension", include_in_schema=False)
async def download_vsix(request: Request):
    user_agent = request.headers.get("user-agent", "unknown")
    client_host = request.client.host if request.client else "127.0.0.1"
    ip_hash = hashlib.sha256(client_host.encode("utf-8")).hexdigest()[:16]
    record_extension_download(user_agent=user_agent, ip_hash=ip_hash, version="1.0.1")

    if os.path.exists(VSIX_PATH):
        return FileResponse(
            VSIX_PATH,
            media_type="application/octet-stream",
            filename="shim-vscode-extension.vsix"
        )
    raise HTTPException(status_code=404, detail="VSIX package not found")

@app.get("/api/downloads/stats")
async def fetch_download_stats():
    """Returns total and unique download counts."""
    return get_download_stats()

# --- Authentication Endpoints ---
@app.post("/api/auth/register")
async def register(req: RegisterRequest):
    conn = get_connection()
    user_id = str(uuid.uuid4())
    pw_hash = hash_password(req.password)
    now = time.time()
    try:
        with conn:
            conn.execute(
                "INSERT INTO users (id, username, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, req.username, req.email, pw_hash, req.role or "customer", now)
            )
    except Exception:
        raise HTTPException(status_code=400, detail="Username or email already registered")

    token = create_session_token(user_id, req.username, req.role or "customer")
    return {
        "token": token,
        "user": {
            "id": user_id,
            "username": req.username,
            "email": req.email,
            "role": req.role or "customer"
        }
    }

@app.post("/api/auth/login")
async def login(req: LoginRequest):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM users WHERE username = ? OR email = ?",
        (req.username_or_email, req.username_or_email)
    ).fetchone()

    if not row or not verify_password(req.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username/email or password")

    user = dict(row)
    token = create_session_token(user["id"], user["username"], user["role"])
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "role": user["role"]
        }
    }

@app.get("/api/auth/me")
async def get_me(user: Dict[str, Any] = Depends(get_current_user)):
    return user

# --- Project & Integration Endpoints ---
@app.get("/api/projects")
async def list_projects(user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_connection()
    if user["role"] == "admin":
        rows = conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
    else:
        rows = conn.execute("SELECT * FROM projects WHERE owner_id = ? ORDER BY created_at DESC", (user["user_id"],)).fetchall()
    return [dict(r) for r in rows]

@app.post("/api/projects")
async def create_new_project(req: CreateProjectRequest, user: Dict[str, Any] = Depends(get_current_user)):
    proj_id = f"proj_{uuid.uuid4().hex[:10]}"
    api_key = f"shim_live_{secrets.token_hex(16)}"
    proj = create_project(proj_id, req.name, user["user_id"], api_key)
    return proj

@app.get("/api/projects/{project_id}")
async def get_project_detail(project_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    proj = get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    if user["role"] != "admin" and proj["owner_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Forbidden")
    return proj

@app.get("/api/projects/{project_id}/integrations")
async def list_integrations(project_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_connection()
    rows = conn.execute("SELECT * FROM integrations WHERE project_id = ?", (project_id,)).fetchall()
    return [dict(r) for r in rows]

@app.post("/api/projects/{project_id}/integrations")
async def create_integration(project_id: str, req: CreateIntegrationRequest, user: Dict[str, Any] = Depends(get_current_user)):
    if not is_safe_target_url(req.target_base_url):
        raise HTTPException(status_code=400, detail="Target URL failed SSRF validation.")
    integ_id = f"int_{uuid.uuid4().hex[:8]}"
    conn = get_connection()
    with conn:
        conn.execute(
            """INSERT INTO integrations (id, project_id, name, target_base_url, auth_token, status, created_at)
               VALUES (?, ?, ?, ?, ?, 'active', ?)""",
            (integ_id, project_id, req.name, req.target_base_url, req.auth_token, time.time())
        )
    return {"id": integ_id, "project_id": project_id, "name": req.name, "target_base_url": req.target_base_url}

# --- Schema, Mapping & History Endpoints ---
@app.get("/api/projects/{project_id}/schemas")
async def get_project_schemas(project_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM endpoint_schemas WHERE project_id = ? ORDER BY created_at DESC",
        (project_id,)
    ).fetchall()
    res = []
    for r in rows:
        d = dict(r)
        d["schema"] = json.loads(d["schema_json"])
        res.append(d)
    return res

@app.get("/api/projects/{project_id}/changes")
async def get_schema_changes(project_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM schema_changes WHERE project_id = ? ORDER BY detected_at DESC",
        (project_id,)
    ).fetchall()
    res = []
    for r in rows:
        d = dict(r)
        d["diff"] = json.loads(d["diff_json"])
        res.append(d)
    return res

@app.get("/api/projects/{project_id}/mappings")
async def get_project_mappings(project_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    return get_mappings_for_project(project_id)

@app.post("/api/mappings/{mapping_id}/approve")
async def approve_mapping(mapping_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_connection()
    row = conn.execute("SELECT * FROM field_mappings WHERE id = ?", (mapping_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Mapping not found")
    proj = get_project(row["project_id"])
    if user["role"] != "admin" and proj["owner_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    ok, msg = approve_mapping_request(mapping_id, row["project_id"], user["user_id"])
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"message": msg, "mapping_id": mapping_id, "status": "APPROVED"}

@app.post("/api/mappings/{mapping_id}/reject")
async def reject_mapping(mapping_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_connection()
    row = conn.execute("SELECT * FROM field_mappings WHERE id = ?", (mapping_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Mapping not found")
    proj = get_project(row["project_id"])
    if user["role"] != "admin" and proj["owner_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    ok, msg = reject_mapping_request(mapping_id, row["project_id"], user["user_id"])
    return {"message": msg, "mapping_id": mapping_id, "status": "REJECTED"}

@app.post("/api/mappings/{mapping_id}/disable")
async def disable_mapping(mapping_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_connection()
    row = conn.execute("SELECT * FROM field_mappings WHERE id = ?", (mapping_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Mapping not found")
    proj = get_project(row["project_id"])
    if user["role"] != "admin" and proj["owner_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    ok, msg = disable_mapping_request(mapping_id, row["project_id"], user["user_id"])
    return {"message": msg, "mapping_id": mapping_id, "status": "DISABLED"}

@app.get("/api/projects/{project_id}/history")
async def get_project_history(project_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM transformation_logs WHERE project_id = ? ORDER BY timestamp DESC LIMIT 100",
        (project_id,)
    ).fetchall()
    res = []
    for r in rows:
        d = dict(r)
        d["original_payload"] = json.loads(d["original_payload"]) if d["original_payload"] else None
        d["transformed_payload"] = json.loads(d["transformed_payload"]) if d["transformed_payload"] else None
        d["mappings_applied"] = json.loads(d["mappings_applied_json"]) if d["mappings_applied_json"] else []
        res.append(d)
    return res

# --- Administrator Endpoints ---
@app.get("/api/admin/overview")
async def get_admin_overview(admin: Dict[str, Any] = Depends(require_admin)):
    conn = get_connection()
    total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_projects = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    total_requests = conn.execute("SELECT COUNT(*) FROM transformation_logs").fetchone()[0]
    total_transformations = conn.execute("SELECT COUNT(*) FROM transformation_logs WHERE transformation_occurred = 1").fetchone()[0]
    pending_mappings = conn.execute("SELECT COUNT(*) FROM field_mappings WHERE status = 'PENDING'").fetchone()[0]
    approved_mappings = conn.execute("SELECT COUNT(*) FROM field_mappings WHERE status = 'APPROVED'").fetchone()[0]
    avg_latency_row = conn.execute("SELECT AVG(latency_ms) FROM transformation_logs").fetchone()[0]
    avg_latency = round(avg_latency_row or 0.0, 2)
    dl_stats = get_download_stats()

    return {
        "status": "healthy",
        "proxy_port": settings.PROXY_PORT,
        "total_users": total_users,
        "total_projects": total_projects,
        "total_requests": total_requests,
        "total_transformations": total_transformations,
        "pending_mappings": pending_mappings,
        "approved_mappings": approved_mappings,
        "avg_latency_ms": avg_latency,
        "total_downloads": dl_stats["total_downloads"],
        "unique_downloaders": dl_stats["unique_downloaders"],
        "model_engine": "Semantic Vector Embedding + Synonym Graph",
        "fallback_status": "Ready & operational"
    }

@app.get("/api/admin/users")
async def get_all_users(admin: Dict[str, Any] = Depends(require_admin)):
    conn = get_connection()
    rows = conn.execute("SELECT id, username, email, role, created_at FROM users ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]

# --- Health check endpoint ---
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "shim_proxy",
        "target_provider": settings.DEFAULT_TARGET_URL,
        "version": settings.VERSION,
        "port": settings.PROXY_PORT
    }

# --- SHIM Core Reverse Proxy Route ---
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
async def handle_proxy(path: str, request: Request):
    if path.startswith("api/") or path.startswith("auth/") or path == "health" or path.startswith("download/") or path in ["console", "admin", "dashboard"]:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    start_time = time.time()

    api_key = request.headers.get("x-api-key")
    if api_key:
        proj = get_project_by_api_key(api_key)
        if not proj:
            raise HTTPException(status_code=401, detail="Invalid API Key")
        project_id = proj["id"]
    else:
        project_id = request.headers.get("x-shim-project-id", "default_project")

    custom_target = request.headers.get("x-shim-target-url")
    target_base = custom_target if custom_target else settings.DEFAULT_TARGET_URL

    if not is_safe_target_url(target_base):
        raise HTTPException(status_code=403, detail="Security Alert: Target URL blocked by SSRF policy.")

    clean_path = f"/{path.lstrip('/')}"
    target_url = f"{target_base.rstrip('/')}{clean_path}"

    params = dict(request.query_params)
    forward_headers = sanitize_headers(dict(request.headers))
    for h in ["x-shim-target-url", "x-shim-project-id", "x-api-key"]:
        forward_headers.pop(h, None)

    body = await request.body()
    timeout_config = httpx.Timeout(timeout=settings.READ_TIMEOUT, connect=settings.CONNECT_TIMEOUT)

    try:
        async with httpx.AsyncClient(timeout=timeout_config) as client:
            upstream_res = await client.request(
                method=request.method,
                url=target_url,
                headers=forward_headers,
                params=params,
                content=body
            )

        latency_ms = round((time.time() - start_time) * 1000, 2)
        content_type = upstream_res.headers.get("content-type", "")
        res_headers = sanitize_headers(dict(upstream_res.headers))

        is_json = "application/json" in content_type
        parsed_json = None
        if is_json:
            try:
                parsed_json = upstream_res.json()
            except Exception:
                logger.warning(f"Upstream returned invalid JSON on {target_url}")
                return Response(
                    content=json.dumps({"error": "Upstream Invalid JSON", "status_code": 502}),
                    status_code=502,
                    media_type="application/json"
                )

        transformed_json = parsed_json
        was_transformed = False
        applied_mappings = []

        if is_json and isinstance(parsed_json, dict) and upstream_res.status_code == 200:
            current_schema = extract_schema(parsed_json)
            current_hash = compute_schema_hash(current_schema)

            latest_schema_record = get_latest_schema(project_id, clean_path)
            if not latest_schema_record:
                save_endpoint_schema(
                    project_id=project_id,
                    endpoint_path=clean_path,
                    version=1,
                    version_tag=f"v1-{current_hash}",
                    schema_hash=current_hash,
                    schema_dict=current_schema,
                    is_baseline=True
                )
            elif latest_schema_record["schema_hash"] != current_hash:
                diff = compare_schemas(latest_schema_record["schema"], current_schema)
                new_version = latest_schema_record["version"] + 1
                save_endpoint_schema(
                    project_id=project_id,
                    endpoint_path=clean_path,
                    version=new_version,
                    version_tag=f"v{new_version}-{current_hash}",
                    schema_hash=current_hash,
                    schema_dict=current_schema,
                    is_baseline=False
                )
                save_schema_change(project_id, clean_path, latest_schema_record["version"], new_version, diff)

                if diff["removed_fields"] and diff["added_fields"]:
                    suggestions = mapping_engine.suggest_mappings(diff["removed_fields"], diff["added_fields"])
                    for s in suggestions:
                        mapping_id = f"map_{uuid.uuid4().hex[:10]}"
                        upsert_mapping(
                            mapping_id=mapping_id,
                            project_id=project_id,
                            endpoint_path=clean_path,
                            source_field=s["source_field"],
                            target_field=s["target_field"],
                            source_type=s["source_type"],
                            target_type=s["target_type"],
                            similarity_score=s["similarity_score"],
                            confidence=s["confidence"],
                            status="PENDING",
                            explanation=s["explanation"]
                        )

            approved_mappings = get_approved_mappings(project_id, clean_path)
            if approved_mappings:
                transformed_json, applied_mappings, was_transformed = transform_response(
                    parsed_json,
                    approved_mappings
                )

            log_transformation(
                project_id=project_id,
                endpoint_path=clean_path,
                method=request.method,
                status_code=upstream_res.status_code,
                original_payload=parsed_json,
                transformed_payload=transformed_json if was_transformed else None,
                mappings_applied=applied_mappings,
                transformation_occurred=was_transformed,
                latency_ms=latency_ms
            )

        res_headers["x-shim-transformed"] = str(was_transformed).lower()
        res_headers["x-shim-mappings-applied"] = str(len(applied_mappings))
        res_headers["x-shim-project-id"] = project_id

        final_content = json.dumps(transformed_json).encode("utf-8") if was_transformed else upstream_res.content
        return Response(
            content=final_content,
            status_code=upstream_res.status_code,
            headers=res_headers,
            media_type=content_type or "application/json"
        )

    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail=f"Bad Gateway: Unable to connect to upstream at {target_base}")
    except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.TimeoutException):
        raise HTTPException(status_code=504, detail="Gateway Timeout: Upstream provider timed out")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Internal Proxy Error: {str(exc)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("proxy:app", host=settings.PROXY_HOST, port=settings.PROXY_PORT, reload=False)
