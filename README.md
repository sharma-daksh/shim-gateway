# SHIM — Adaptive API Compatibility Platform

> **Zero-Downtime API Evolution Proxy & Intelligence Gateway**  
> Sits between client applications and third-party APIs to detect breaking payload changes, intelligently deduce field equivalencies using semantic subword embeddings, enforce human-in-the-loop approvals, and transparently transform API responses in real time.

---

## 1. Architectural Overview

When third-party payment gateways, banking APIs, or SaaS providers alter their response payloads without notice, client applications crash. SHIM eliminates this API fragility:

```
[ Client Application ] 
       │ (expects: {"payment_id": "P101", "price": 500, "status": "success"})
       ▼
┌────────────────────────────────────────────────────────────────────────┐
│  SHIM ADAPTIVE PROXY (:8000)                                          │
│                                                                        │
│  1. Ingress Filter & SSRF Protection                                   │
│  2. Schema Detection Engine (Recursive Tree Diff & Hash Registry)      │
│  3. Intelligent Field Mapping (Semantic Subword Embeddings + Priors)   │
│  4. Validation & Approval State Machine (Pending/Approved/Rejected)   │
│  5. Transformation Engine (Non-destructive JSON restructuring)        │
│  6. SQLite Persistence & Telemetry Logging                             │
└────────────────────────────────────────────────────────────────────────┘
       │ (upstream returns: {"payment_id": "P101", "amount": 500, "status": "success"})
       ▼
[ External API / Mock Payment Provider (:8001) ]
```

---

## 2. Technology Stack

* **Backend Runtime**: Python 3.13 / 3.11
* **API Framework**: FastAPI, Uvicorn, Starlette
* **HTTP Client**: HTTPX (Async & Sync Connection Pooling)
* **Data Validation**: Pydantic
* **Persistence**: SQLite (with relational foreign keys & WAL journaling)
* **AI/ML Engine**: Semantic character n-gram subword embeddings, vector cosine similarity, domain synonym graphs, and structural type compatibility matrix
* **Frontend**: Dark Liquid Chrome Editorial UI (served directly at `http://127.0.0.1:8000/app` and standalone React/Vite/TypeScript in `frontend/`)
* **Testing**: Python unittest / Pytest (53 automated tests across 9 phases)

---

## 3. Directory Structure

```
SHIM/
├── backend/
│   ├── config.py             # Environment settings & timeouts
│   ├── security.py           # SSRF validation & header sanitization
│   ├── database.py           # SQLite relational persistence layer
│   ├── schema_detector.py    # Recursive JSON tree extraction & diffing
│   ├── mapping_engine.py     # Subword embedding & semantic matching
│   ├── mapping_service.py    # Validation & approval lifecycle
│   ├── transformer.py        # Safe response rewriting engine
│   ├── auth.py               # PBKDF2 hashing & session tokens
│   ├── proxy.py              # Main reverse proxy & REST endpoints
│   ├── mock_provider.py      # Upstream payment API simulator
│   ├── benchmark.py          # 4-tier performance benchmark suite
│   ├── static/
│   │   └── index.html        # Dark Liquid Chrome Single-Page Application
│   └── tests/
│       ├── test_phase0_audit.py
│       ├── test_phase1_foundation.py
│       ├── test_phase2_schema_detection.py
│       ├── test_phase3_database.py
│       ├── test_phase4_mapping_engine.py
│       ├── test_phase5_approval.py
│       ├── test_phase6_transformation.py
│       ├── test_phase7_integration.py
│       ├── test_phase8_auth_security.py
│       └── test_phase9_10_frontend_api.py
├── frontend/                 # React + Vite + TypeScript application
└── README.md
```

---

## 4. Quick Start (Windows & PowerShell)

### Step 1: Virtual Environment Setup
```powershell
# Create venv
python -m venv .venv

# Install dependencies
.\.venv\Scripts\pip.exe install fastapi uvicorn httpx pydantic
```

### Step 2: Start Services
Open two terminal windows:

* **Terminal 1 (Mock Upstream Provider)**:
  ```powershell
  .\.venv\Scripts\python.exe backend\mock_provider.py
  ```
  *Runs on `http://127.0.0.1:8001`*

* **Terminal 2 (SHIM Adaptive Proxy & UI)**:
  ```powershell
  .\.venv\Scripts\python.exe backend\proxy.py
  ```
  *Runs on `http://127.0.0.1:8000`*

### Step 3: Open the Dark Liquid Chrome Web Interface
Open your browser to:
👉 **`http://127.0.0.1:8000/app`**

Default credentials:
* **Username**: `admin`
* **Password**: `admin123`

---

## 5. Running Automated Tests

Run the complete test suite (53 tests across all phases):
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend\tests -p "test_*.py"
```
Or via pytest:
```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

---

## 6. Real-World Benchmark Results

Benchmarks measured across 50 consecutive iterations per tier using `backend/benchmark.py`:

| Tier / Architectural Mode | Mean Latency | p50 | p95 | Accuracy / Success |
| :--- | :---: | :---: | :---: | :---: |
| **1. Direct API (No Proxy)** | 0.73 ms | 0.69 ms | 0.92 ms | 100% (Baseline) |
| **2. Basic SHIM Proxy** | 30.86 ms | 30.02 ms | 34.97 ms | 100% Forwarding |
| **3. AI Semantic Inference** | 0.02 ms | 0.02 ms | 0.03 ms | 100% Precision / Recall |
| **4. Approved Deterministic SHIM** | < 0.01 ms | < 0.01 ms | 0.01 ms | 100.0% Transformation |

### Key Benchmark Insights
* **Zero Overhead on Approved Transformations**: Once an intelligent mapping is approved, subsequent transformations occur in sub-millisecond memory execution without running expensive embedding models on every request.
* **Deterministic Safety**: No artificial data fabrication occurs. If an incoming response is missing an expected field, SHIM preserves structural integrity rather than hallucinating financial values.

---

## 7. Security & Governance

1. **SSRF Guard**: Strict validation against loopback, cloud instance metadata endpoints (`169.254.169.254`), and forbidden URI schemes (`file://`, `gopher://`).
2. **Cryptographic Protection**: Passwords hashed using PBKDF2-HMAC-SHA256 with 100,000 iterations and 16-byte random salts.
3. **Multi-Tenant Data Isolation**: Projects and schema histories are partitioned by API keys (`shim_live_...`). Customer accounts cannot inspect or modify peers' schemas or mapping configurations.
4. **Header Sanitization**: Hop-by-hop headers (`Connection`, `Keep-Alive`, `Transfer-Encoding`) are stripped to prevent connection smuggling.
