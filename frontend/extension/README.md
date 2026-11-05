# SHIM — Adaptive API Compatibility Guard

A real-time developer guard that sits between your application and external APIs to intercept breaking JSON schema changes, infer field replacements using subword vector embeddings, and transparently auto-bridge payloads without code crashes.

## Features

- **Status Bar Health**: Real-time indicator displaying gateway status directly in VS Code.
- **Breaking Drift Interception**: Detects renamed, added, or removed JSON fields on upstream REST responses.
- **One-Click Schema Bridge**: Approve proposed field mappings directly or via the web platform.
- **Universal API Support**: Protects user profiles, payments, shipping, logistics, or custom microservices.

## Getting Started

1. Start your local SHIM Gateway (or connect to a cloud deployment):
   ```bash
   python backend/proxy.py
   ```
2. In VS Code Settings (`Ctrl+,`), search for **SHIM**:
   - `shim.gatewayUrl`: defaults to `http://127.0.0.1:8000`
   - `shim.apiKey`: your project API key
3. Press `Ctrl+Shift+P` and type **SHIM: Scan Connected APIs for Schema Drift** to verify your setup.

## License

MIT © Daksh Sharma
