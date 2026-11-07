/**
 * Automated verification test suite for shim-gateway
 */

const assert = require('assert');
const { ShimClient, createShimClient, shimFetch, DEFAULT_GATEWAY_URL, DEFAULT_API_KEY } = require('./index.js');

console.log('Testing shim-gateway package exports and client...\n');

// 1. Verify exports
assert.strictEqual(typeof ShimClient, 'function', 'ShimClient should be a class constructor');
assert.strictEqual(typeof createShimClient, 'function', 'createShimClient should be a factory function');
assert.strictEqual(typeof shimFetch, 'function', 'shimFetch should be an async function');
assert.strictEqual(DEFAULT_GATEWAY_URL, 'https://shim-gateway.onrender.com');
assert.strictEqual(DEFAULT_API_KEY, 'shim_live_default_key');
console.log('✔ Exports verified.');

// 2. Verify default client initialization
const client = new ShimClient();
assert.strictEqual(client.gatewayUrl, 'https://shim-gateway.onrender.com');
assert.strictEqual(client.apiKey, 'shim_live_default_key');
assert.strictEqual(client.timeout, 10000);
console.log('✔ Default client initialization verified.');

// 3. Verify custom options
const customClient = createShimClient({
  gatewayUrl: 'http://127.0.0.1:8000/',
  apiKey: 'custom_key_999',
  timeout: 5000,
  headers: { 'X-Custom-Env': 'test' }
});
assert.strictEqual(customClient.gatewayUrl, 'http://127.0.0.1:8000', 'Trailing slash should be trimmed');
assert.strictEqual(customClient.apiKey, 'custom_key_999');
assert.strictEqual(customClient.timeout, 5000);
assert.strictEqual(customClient.defaultHeaders['X-Custom-Env'], 'test');
console.log('✔ Custom options and URL trimming verified.');

// 4. Verify URL building
const url1 = client._buildUrl('/payments/P101');
const url2 = client._buildUrl('payments/P101');
assert.strictEqual(url1, 'https://shim-gateway.onrender.com/payments/P101');
assert.strictEqual(url2, 'https://shim-gateway.onrender.com/payments/P101');
console.log('✔ Path normalisation verified.');

// 5. Verify methods existence
assert.strictEqual(typeof client.request, 'function');
assert.strictEqual(typeof client.get, 'function');
assert.strictEqual(typeof client.post, 'function');
assert.strictEqual(typeof client.put, 'function');
assert.strictEqual(typeof client.patch, 'function');
assert.strictEqual(typeof client.delete, 'function');
assert.strictEqual(typeof client.checkHealth, 'function');
console.log('✔ Client methods verified.');

console.log('\nAll tests passed successfully! 🚀');
