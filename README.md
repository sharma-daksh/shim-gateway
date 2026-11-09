# SHIM — Adaptive API Compatibility Platform

> **Zero-Downtime API Evolution Proxy & Intelligence Gateway**  
> Sits between client applications and upstream APIs to detect breaking payload changes, intelligently deduce field equivalencies using semantic subword embeddings, enforce human-in-the-loop approvals, and transparently transform API responses in real time.

[](https://shim-gateway.onrender.com)
[](https://www.npmjs.com/package/shim-gateway)
[VS Code Marketplace](https://www.google.com/search?q=https://marketplace.visualstudio.com/manage/publishers/sharma-daksh)
[](https://opensource.org/licenses/MIT)

---

## 1. Architectural Overview

When third-party payment gateways, microservices, or external APIs alter their response payloads without notice, client applications crash. SHIM eliminates this API fragility:

```
[ Client Application ] 
       │ (expects: {"user_id": "U101", "created_at": "2026-11-09", "status": "active"})
       ▼
┌────────────────────────────────────────────────────────────────────────┐
│  SHIM ADAPTIVE PROXY (:8000)                                          │
│                                                                        │
│  1. Ingress Filter & SSRF Protection                                   │
│  2. Schema Detection Engine (Recursive Tree Diff & Hash Registry)      │
│  3. Intelligent Field Mapping (Subword Character N-Gram Embeddings)    │
│  4. Validation & Type Guard State Machine (Pending / Approved)         │
│  5. Transformation Engine (Non-destructive JSON restructuring)        │
│  6. SQLite Persistence & Drift Telemetry Logging                       │
└────────────────────────────────────────────────────────────────────────┘
       │ (upstream returns: {"id": "U101", "timestamp": "2026-11-09", "status": "active"})
       ▼
[ External Upstream API / Mock Service (:8001) ]
```

---

## 2. Technology Stack

* **Backend Runtime**: Python 3.11 / 3.13
* **API Framework**: FastAPI, Uvicorn, Starlette
* **HTTP Client**: HTTPX (Async Connection Pooling)
* **Data Validation**: Pydantic
* **Persistence**: SQLite (with relational foreign keys & WAL journaling)
* **AI/ML Engine**: Subword character n-gram vector embeddings, cosine similarity, domain synonym graphs, and structural type compatibility matrices
* **Frontend**: Dark Liquid Chrome Editorial Landing Page (`frontend/index.html`) & Developer Console (`frontend/console.html`)
* **Developer Tooling**: Visual Studio Code Extension (`v1.0.1`) & NPM Universal Client/CLI (`shim-gateway`)
* **Testing**: Python unittest / Pytest (71 automated tests passing 100% across all 11 phases)

---

## 3. Directory Structure

```
SHIM/
├── backend/
│   ├── config.py             # Environment settings & timeouts
│   ├── security.py           # SSRF validation & header sanitization
│   ├── database.py           # SQLite relational persistence layer (shim.db)
│   ├── schema_detector.py    # Recursive JSON tree extraction & diffing
│   ├── mapping_engine.py     # Subword embedding & semantic matching
│   ├── mapping_service.py    # Validation & approval lifecycle
│   ├── transformer.py        # Safe response rewriting engine
│   ├── auth.py               # PBKDF2 hashing & session tokens
│   ├── proxy.py              # Main reverse proxy, REST endpoints & static routes
│   ├── mock_provider.py      # Upstream payment & user API simulator
│   ├── benchmark.py          # 4-tier performance benchmark suite
│   └── tests/                # 71 automated unit & integration tests
│       ├── test_phase0_audit.py
│       ├── test_phase1_foundation.py
│       ├── test_phase2_schema_detection.py
│       ├── test_phase3_database.py
│       ├── test_phase4_mapping_engine.py
│       ├── test_phase5_approval.py
│       ├── test_phase6_transformation.py
│       ├── test_phase7_integration.py
│       ├── test_phase8_auth_security.py
│       ├── test_phase9_10_frontend_api.py
│       └── test_phase11_production.py
├── frontend/
│   ├── index.html            # Public Dark Liquid Chrome landing website
│   ├── console.html          # Balanced 2-column local Developer Console
│   └── public/
│       └── shim-vscode-extension.vsix # Packaged VS Code extension
├── npm/                      # NPM Package (shim-gateway v1.0.0)
│   ├── bin/cli.js            # Executable CLI utility
│   ├── index.js              # Universal zero-dependency client
│   ├── index.mjs             # ES Module entry point
│   ├── index.d.ts            # Complete TypeScript typings
│   ├── package.json          # Package manifest
│   └── README.md             # NPM documentation
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

### Step 3: Open the Web Interfaces
* **Public Landing Page & Interactive Scanner**: `http://127.0.0.1:8000/`
* **Local Developer Console**: `http://127.0.0.1:8000/console`

---

## 5. NPM Client & CLI

You can install the official client or run diagnostics directly via NPM:

```bash
# Install in your project
npm install shim-gateway

# Quick health check without installing
npx shim-gateway status
```

Example in Node.js / TypeScript:
```typescript
import { createShimClient } from 'shim-gateway';

const shim = createShimClient({
  gatewayUrl: 'https://shim-gateway.onrender.com'
});

const user = await shim.get('/v1/users/101');
console.log(user);
```

---

## 6. Running Automated Tests

Run the complete test suite (71 tests across all 11 phases):
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend\tests -p "test_*.py"
```

Or via pytest:
```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

---

## 7. Real-World Benchmark Results

Benchmarks measured across 50 consecutive iterations per tier using `backend/benchmark.py`:

| Tier / Architectural Mode | Mean Latency | p50 | p95 | Accuracy / Success |
| :--- | :---: | :---: | :---: | :---: |
| **1. Direct API (No Proxy)** | 0.73 ms | 0.69 ms | 0.92 ms | 100% (Baseline) |
| **2. Basic SHIM Proxy** | 30.86 ms | 30.02 ms | 34.97 ms | 100% Forwarding |
| **3. AI Semantic Inference** | 0.02 ms | 0.02 ms | 0.03 ms | 100% Precision / Recall |
| **4. Approved Deterministic SHIM** | < 0.01 ms | < 0.01 ms | 0.01 ms | 100.0% Transformation |

---

## 8. Security & Governance

1. **SSRF Guard**: Strict validation against loopback, cloud instance metadata endpoints (`169.254.169.254`), and forbidden URI schemes (`file://`, `gopher://`).
2. **Cryptographic Protection**: Passwords hashed using PBKDF2-HMAC-SHA256 with 100,000 iterations and 16-byte random salts.
3. **Multi-Tenant Data Isolation**: Projects and schema histories are partitioned by API keys (`shim_live_...`). Customer accounts cannot inspect or modify peers' schemas or mapping configurations.
4. **Header Sanitization**: Hop-by-hop headers (`Connection`, `Keep-Alive`, `Transfer-Encoding`) are stripped to prevent connection smuggling.

---

## 9. Ecosystem Links

* **Live Cloud Deployment**: [https://shim-gateway.onrender.com](https://shim-gateway.onrender.com)
* **NPM Package**: [https://www.npmjs.com/package/shim-gateway](https://www.npmjs.com/package/shim-gateway)
* **VS Code Marketplace**: [Sharma Daksh on Visual Studio Marketplace](https://www.google.com/search?q=https://marketplace.visualstudio.com/manage/publishers/sharma-daksh)
* **Author**: Daksh Sharma ([GitHub](https://github.com/sharma-daksh) • [LinkedIn](https://www.linkedin.com/in/daksh-sharma-d/))
