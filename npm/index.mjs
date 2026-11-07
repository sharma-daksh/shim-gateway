/**
 * ES Module Entry Point for shim-gateway
 */
import cjs from './index.js';

export const ShimClient = cjs.ShimClient;
export const createShimClient = cjs.createShimClient;
export const shimFetch = cjs.shimFetch;
export const DEFAULT_GATEWAY_URL = cjs.DEFAULT_GATEWAY_URL;
export const DEFAULT_API_KEY = cjs.DEFAULT_API_KEY;

export default cjs;
