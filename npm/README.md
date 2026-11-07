# shim-gateway

> **Zero-downtime adaptive API compatibility client and CLI.**  
> Automatically detects breaking upstream changes, bridges drifted payload schemas with subword semantic matching, and prevents downstream crashes in Node.js, Next.js, React, and TypeScript applications.

[![NPM Version](https://img.shields.io/npm/v/shim-gateway.svg?style=flat-square&color=E63946)](https://www.npmjs.com/package/shim-gateway)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](https://opensource.org/licenses/MIT)
[![VS Code Marketplace](https://img.shields.io/badge/VS_Code-v1.0.1_Active-007ACC?style=flat-square&logo=visual-studio-code)](https://marketplace.visualstudio.com/manage/publishers/sharma-daksh)
[![Gateway](https://img.shields.io/badge/Live_Gateway-Render_Online-brightgreen?style=flat-square)](https://shim-gateway.onrender.com)

---

## What is SHIM?

Modern microservices, payment gateways, and third-party APIs change field names and structures without warning (`payment_id` becomes `transactionId`, `amount_cents` becomes `amountInSubunits`). Traditional solutions require emergency engineering tickets, patch deployments, and downtime.

**SHIM** acts as an adaptive neural proxy layer between your client and target services:
- **Zero Configuration**: Works as a drop-in replacement for standard `fetch` or SDK clients.
- **Auto-Bridging**: Automatically transforms drifted responses back to the expected contract before your app crashes.
- **Telemetry & Inspection**: Returns headers showing whether a payload was transformed and which mappings were applied (`x-shim-transformed`, `x-shim-mappings-applied`).
- **Zero External Dependencies**: Pure native ESM and CommonJS with built-in TypeScript declarations.

---

## Installation

```bash
npm install shim-gateway
# or with pnpm / yarn / bun
pnpm add shim-gateway
yarn add shim-gateway
bun add shim-gateway
```

---

## Quickstart

### 1. Simple Drop-In Fetch

```javascript
import { shimFetch } from 'shim-gateway';

// Makes request through the live SHIM adaptive gateway
const result = await shimFetch('/payments/P101');

console.log('API Data:', result.data);
console.log('Was Payload Transformed:', result.isTransformed);
console.log('Mappings Applied:', result.mappingsApplied);
```

### 2. Client Instance (Recommended for Apps & Next.js)

```typescript
import { createShimClient } from 'shim-gateway';

const shim = createShimClient({
  // Default points to live cloud gateway: 'https://shim-gateway.onrender.com'
  // Or your local proxy: 'http://127.0.0.1:8000'
  gatewayUrl: process.env.SHIM_GATEWAY_URL || 'https://shim-gateway.onrender.com',
  apiKey: process.env.SHIM_API_KEY || 'shim_live_default_key',
  timeout: 8000 // 8 second timeout
});

// GET request
const payment = await shim.get('/payments/P101');
console.log(payment.payment_id, payment.status);

// POST request
const newOrder = await shim.post('/orders', {
  items: ['sku_101'],
  currency: 'USD'
});
```

### 3. Full Request with Detailed Telemetry

```typescript
const { data, response, isTransformed, mappingsApplied, latencyMs } = await shim.request('/v1/users/42');

if (isTransformed) {
  console.warn(`[SHIM] Upstream API schema drifted! Auto-bridged ${mappingsApplied} fields in ${latencyMs}ms.`);
}
```

---

## CLI Usage

You can run SHIM commands directly without installing using `npx`:

```bash
# Check status of the active SHIM Gateway
npx shim-gateway status

# Probe an API path to check for schema drift
npx shim-gateway scan /health

# Connect to a local developer gateway
npx shim-gateway status --gateway http://127.0.0.1:8000
```

Or install globally to use the short `shim` command:

```bash
npm install -g shim-gateway

shim status
shim scan /payments/P101
```

---

## TypeScript Support

Full TypeScript typings are bundled out-of-the-box:

```typescript
import { ShimClient, ShimClientOptions, ShimRequestResult } from 'shim-gateway';

interface PaymentResponse {
  payment_id: string;
  amount: number;
  currency: string;
  status: string;
}

const client = new ShimClient();
const payment = await client.get<PaymentResponse>('/payments/P101');
```

---

## Ecosystem

- **Live Cloud Gateway & Web Console**: [https://shim-gateway.onrender.com](https://shim-gateway.onrender.com)
- **VS Code Extension**: [Sharma Daksh on Visual Studio Marketplace](https://marketplace.visualstudio.com/manage/publishers/sharma-daksh)
- **GitHub Repository**: [https://github.com/sharma-daksh/shim-gateway](https://github.com/sharma-daksh/shim-gateway)

---

## Author & License

- **Author**: [Daksh Sharma](https://github.com/sharma-daksh) ([LinkedIn](https://www.linkedin.com/in/daksh-sharma-d/))
- **Email**: daksh018@outlook.com
- **License**: MIT
