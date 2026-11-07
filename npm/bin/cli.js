#!/usr/bin/env node

/**
 * shim-gateway CLI
 * Command line utility for the SHIM Adaptive API Platform
 * Author: Daksh Sharma (https://github.com/sharma-daksh)
 */

const { ShimClient, DEFAULT_GATEWAY_URL } = require('../index.js');
const pkg = require('../package.json');

const args = process.argv.slice(2);
const command = args[0] || '--help';

const BANNER = `
  ⚡ SHIM CLI — Adaptive API Compatibility Engine v${pkg.version}
  Live Gateway: ${DEFAULT_GATEWAY_URL}
`;

function printHelp() {
  console.log(BANNER);
  console.log(`Usage:
  npx shim-gateway <command> [options]
  shim <command> [options]

Commands:
  status, health          Check connectivity to the active SHIM Gateway
  scan <url>              Send a probe request through the gateway to inspect payload schema
  version, -v, --version  Show CLI and package version
  help, -h, --help        Show this help message

Options:
  --gateway <url>         Override gateway URL (default: ${DEFAULT_GATEWAY_URL})
  --key <api-key>         Specify project API key
  --timeout <ms>          Set request timeout in milliseconds (default: 10000)

Examples:
  npx shim-gateway status
  npx shim-gateway status --gateway http://127.0.0.1:8000
  npx shim-gateway scan /health
  shim status
`);
}

function parseFlags(argv) {
  const flags = {
    gateway: DEFAULT_GATEWAY_URL,
    apiKey: 'shim_live_default_key',
    timeout: 10000
  };

  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--gateway' && argv[i + 1]) {
      flags.gateway = argv[i + 1];
      i++;
    } else if (argv[i] === '--key' && argv[i + 1]) {
      flags.apiKey = argv[i + 1];
      i++;
    } else if (argv[i] === '--timeout' && argv[i + 1]) {
      flags.timeout = parseInt(argv[i + 1], 10);
      i++;
    }
  }

  return flags;
}

async function handleHealth(flags) {
  console.log(BANNER);
  console.log(`Connecting to SHIM Gateway at: ${flags.gateway} ...\n`);
  const client = new ShimClient({ gatewayUrl: flags.gateway, timeout: flags.timeout });
  const start = Date.now();

  try {
    const res = await client.checkHealth();
    const elapsed = Date.now() - start;
    console.log(`✔ Gateway Online!`);
    console.log(`  • Service:   ${res.service || 'shim-proxy'}`);
    console.log(`  • Status:    ${res.status || 'healthy'}`);
    console.log(`  • Latency:   ${elapsed}ms`);
    console.log(`  • Target:    ${flags.gateway}`);
  } catch (err) {
    console.error(`✖ Gateway Connection Failed!`);
    console.error(`  • Error:   ${err.message}`);
    console.error(`\nPlease ensure the SHIM Gateway is running locally (e.g. uvicorn backend.proxy:app) or check your network.`);
    process.exit(1);
  }
}

async function handleScan(targetPath, flags) {
  if (!targetPath) {
    console.error('Error: Please specify a path to scan (e.g. shim scan /health or shim scan /payments/P101)');
    process.exit(1);
  }

  console.log(BANNER);
  console.log(`Sending inspection probe through SHIM Gateway to '${targetPath}' ...\n`);
  const client = new ShimClient({
    gatewayUrl: flags.gateway,
    apiKey: flags.apiKey,
    timeout: flags.timeout
  });

  try {
    const result = await client.request(targetPath);
    console.log(`✔ Response Received (${result.latencyMs}ms):`);
    console.log(`  • Transformed:        ${result.isTransformed ? 'YES (Auto-bridged drift)' : 'NO (Original schema)'}`);
    console.log(`  • Mappings Applied:   ${result.mappingsApplied}`);
    console.log(`  • HTTP Status:        ${result.response.status}`);
    console.log(`\nPayload:`);
    console.log(JSON.stringify(result.data, null, 2));
  } catch (err) {
    console.error(`✖ Probe Failed: ${err.message}`);
    process.exit(1);
  }
}

async function main() {
  const flags = parseFlags(args);

  switch (command) {
    case 'status':
    case 'health':
      await handleHealth(flags);
      break;

    case 'scan':
      await handleScan(args[1], flags);
      break;

    case '-v':
    case '--version':
    case 'version':
      console.log(`v${pkg.version}`);
      break;

    case '-h':
    case '--help':
    case 'help':
    default:
      printHelp();
      break;
  }
}

main().catch(err => {
  console.error('CLI Fatal Error:', err);
  process.exit(1);
});
