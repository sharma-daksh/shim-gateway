/**
 * shim-gateway — Adaptive API Compatibility Client
 * Zero-dependency universal client for Node.js, Next.js, React, and browser environments.
 * Author: Daksh Sharma (https://github.com/sharma-daksh)
 * License: MIT
 */

const DEFAULT_GATEWAY_URL = 'https://shim-gateway.onrender.com';
const DEFAULT_API_KEY = 'shim_live_default_key';

class ShimClient {
  /**
   * @param {Object} options
   * @param {string} [options.gatewayUrl] - Gateway base URL (defaults to live Render gateway or localhost)
   * @param {string} [options.apiKey] - Project API key
   * @param {number} [options.timeout] - Timeout in milliseconds (default: 10000ms)
   * @param {Object} [options.headers] - Global headers to merge with every request
   */
  constructor(options = {}) {
    this.gatewayUrl = (options.gatewayUrl || DEFAULT_GATEWAY_URL).replace(/\/$/, '');
    this.apiKey = options.apiKey || DEFAULT_API_KEY;
    this.timeout = options.timeout || 10000;
    this.defaultHeaders = options.headers || {};
  }

  /**
   * Format target path and build destination URL
   * @private
   */
  _buildUrl(path) {
    const cleanPath = path.startsWith('/') ? path : `/${path}`;
    return `${this.gatewayUrl}${cleanPath}`;
  }

  /**
   * Universal fetch wrapper with automatic timeout and header injection
   * @param {string} path - Target API path (e.g. '/payments/P101' or '/v1/users')
   * @param {Object} [init] - Standard RequestInit options (method, body, headers, etc.)
   * @returns {Promise<{data: any, response: Response, isTransformed: boolean, mappingsApplied: number, latencyMs: number}>}
   */
  async request(path, init = {}) {
    const url = this._buildUrl(path);
    const method = (init.method || 'GET').toUpperCase();
    const headers = {
      'Accept': 'application/json',
      'X-API-Key': this.apiKey,
      ...this.defaultHeaders,
      ...(init.headers || {})
    };

    if (init.body && typeof init.body === 'object' && !(init.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(init.body);
    }

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeout);

    const startTime = performance.now();
    try {
      const response = await fetch(url, {
        ...init,
        method,
        headers,
        signal: controller.signal
      });

      clearTimeout(timer);
      const latencyMs = Math.round(performance.now() - startTime);

      const contentType = response.headers.get('content-type') || '';
      let data = null;
      if (contentType.includes('application/json')) {
        data = await response.json();
      } else {
        data = await response.text();
      }

      const isTransformed = response.headers.get('x-shim-transformed') === 'true';
      const mappingsApplied = parseInt(response.headers.get('x-shim-mappings-applied') || '0', 10);

      if (!response.ok) {
        const error = new Error(`SHIM Gateway HTTP ${response.status}: ${typeof data === 'object' ? JSON.stringify(data) : data}`);
        error.status = response.status;
        error.data = data;
        error.response = response;
        throw error;
      }

      return {
        data,
        response,
        isTransformed,
        mappingsApplied,
        latencyMs
      };
    } catch (err) {
      clearTimeout(timer);
      if (err.name === 'AbortError') {
        throw new Error(`SHIM Gateway Timeout: Request to '${url}' exceeded ${this.timeout}ms`);
      }
      throw err;
    }
  }

  /**
   * Convenience GET request returning directly transformed payload
   * @param {string} path
   * @param {Object} [init]
   * @returns {Promise<any>}
   */
  async get(path, init = {}) {
    const res = await this.request(path, { ...init, method: 'GET' });
    return res.data;
  }

  /**
   * Convenience POST request returning directly transformed payload
   * @param {string} path
   * @param {any} body
   * @param {Object} [init]
   * @returns {Promise<any>}
   */
  async post(path, body, init = {}) {
    const res = await this.request(path, { ...init, method: 'POST', body });
    return res.data;
  }

  /**
   * Convenience PUT request
   */
  async put(path, body, init = {}) {
    const res = await this.request(path, { ...init, method: 'PUT', body });
    return res.data;
  }

  /**
   * Convenience PATCH request
   */
  async patch(path, body, init = {}) {
    const res = await this.request(path, { ...init, method: 'PATCH', body });
    return res.data;
  }

  /**
   * Convenience DELETE request
   */
  async delete(path, init = {}) {
    const res = await this.request(path, { ...init, method: 'DELETE' });
    return res.data;
  }

  /**
   * Health check query to test connectivity to the SHIM Gateway
   * @returns {Promise<{status: string, service: string, port: number}>}
   */
  async checkHealth() {
    const url = `${this.gatewayUrl}/health`;
    const res = await fetch(url);
    return res.json();
  }
}

/**
 * Factory helper function to create a new ShimClient instance
 * @param {Object} [options]
 * @returns {ShimClient}
 */
function createShimClient(options = {}) {
  return new ShimClient(options);
}

/**
 * Direct drop-in fetch interceptor
 * @param {string} path
 * @param {RequestInit} [init]
 * @param {Object} [clientOptions]
 */
async function shimFetch(path, init = {}, clientOptions = {}) {
  const client = new ShimClient(clientOptions);
  return client.request(path, init);
}

module.exports = {
  ShimClient,
  createShimClient,
  shimFetch,
  DEFAULT_GATEWAY_URL,
  DEFAULT_API_KEY
};
