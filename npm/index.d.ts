/**
 * TypeScript Type Definitions for shim-gateway
 */

export interface ShimClientOptions {
  /**
   * Target SHIM Gateway URL.
   * Defaults to live cloud gateway: 'https://shim-gateway.onrender.com'
   * Or local gateway: 'http://127.0.0.1:8000'
   */
  gatewayUrl?: string;

  /**
   * Project API key. Defaults to 'shim_live_default_key'.
   */
  apiKey?: string;

  /**
   * Request timeout in milliseconds (default: 10000ms).
   */
  timeout?: number;

  /**
   * Custom headers merged with every request.
   */
  headers?: Record<string, string>;
}

export interface ShimRequestResult<T = any> {
  /**
   * Transformed JSON or text response body.
   */
  data: T;

  /**
   * Raw Fetch Response instance.
   */
  response: Response;

  /**
   * True if SHIM intercepted an upstream breaking change and auto-transformed the payload.
   */
  isTransformed: boolean;

  /**
   * Number of field mappings applied.
   */
  mappingsApplied: number;

  /**
   * Roundtrip gateway latency in milliseconds.
   */
  latencyMs: number;
}

export declare class ShimClient {
  constructor(options?: ShimClientOptions);

  readonly gatewayUrl: string;
  readonly apiKey: string;
  readonly timeout: number;
  readonly defaultHeaders: Record<string, string>;

  /**
   * Perform raw HTTP request through SHIM Gateway with telemetry metadata.
   */
  request<T = any>(path: string, init?: RequestInit): Promise<ShimRequestResult<T>>;

  /**
   * Perform GET request and return transformed JSON payload directly.
   */
  get<T = any>(path: string, init?: RequestInit): Promise<T>;

  /**
   * Perform POST request with body.
   */
  post<T = any>(path: string, body?: any, init?: RequestInit): Promise<T>;

  /**
   * Perform PUT request with body.
   */
  put<T = any>(path: string, body?: any, init?: RequestInit): Promise<T>;

  /**
   * Perform PATCH request with body.
   */
  patch<T = any>(path: string, body?: any, init?: RequestInit): Promise<T>;

  /**
   * Perform DELETE request.
   */
  delete<T = any>(path: string, init?: RequestInit): Promise<T>;

  /**
   * Verify gateway connectivity.
   */
  checkHealth(): Promise<{ status: string; service: string; port: number }>;
}

export declare function createShimClient(options?: ShimClientOptions): ShimClient;

export declare function shimFetch<T = any>(
  path: string,
  init?: RequestInit,
  clientOptions?: ShimClientOptions
): Promise<ShimRequestResult<T>>;

export declare const DEFAULT_GATEWAY_URL: string;
export declare const DEFAULT_API_KEY: string;
