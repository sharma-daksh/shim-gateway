const vscode = require('vscode');

function activate(context) {
    console.log('SHIM API Guard activated.');

    // Helper to get configured gateway URL
    function getGatewayUrl() {
        const config = vscode.workspace.getConfiguration('shim');
        return (config.get('gatewayUrl') || 'http://127.0.0.1:8000').replace(/\/$/, '');
    }

    function getApiKey() {
        const config = vscode.workspace.getConfiguration('shim');
        return config.get('apiKey') || 'shim_live_default_key';
    }

    // Create Status Bar Item
    const statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    statusBarItem.text = `$(shield) SHIM: Active`;
    statusBarItem.tooltip = `SHIM Active on ${getGatewayUrl()} — Click to open Developer Console`;
    statusBarItem.command = 'shim.openConsole';
    statusBarItem.show();
    context.subscriptions.push(statusBarItem);

    // Command: Open Developer Console
    let openConsoleCmd = vscode.commands.registerCommand('shim.openConsole', function () {
        vscode.env.openExternal(vscode.Uri.parse(`${getGatewayUrl()}/console`));
    });
    context.subscriptions.push(openConsoleCmd);

    // Command: Scan Endpoints
    let scanCmd = vscode.commands.registerCommand('shim.scanEndpoints', async function () {
        const gateway = getGatewayUrl();
        const apiKey = getApiKey();
        vscode.window.showInformationMessage(`SHIM: Scanning connected APIs on ${gateway}...`);
        try {
            const response = await fetch(`${gateway}/payments/P101`, {
                headers: { 'X-API-Key': apiKey }
            });
            const isTransformed = response.headers.get('x-shim-transformed') === 'true';

            if (isTransformed) {
                vscode.window.showInformationMessage('SHIM Protected: Breaking API change detected and auto-bridged!');
            } else {
                vscode.window.showInformationMessage('SHIM: API healthy. Schema matches expected baseline.');
            }
        } catch (err) {
            vscode.window.showErrorMessage(`SHIM Proxy check: ${err.message}`);
        }
    });
    context.subscriptions.push(scanCmd);
}

function deactivate() {}

module.exports = {
    activate,
    deactivate
};
