import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: '../../tests/e2e', timeout: 30000, workers: 1,
  reporter: 'list', use: { baseURL: 'http://127.0.0.1:1420', channel: 'msedge', headless: true,
    viewport: { width: 1280, height: 860 }, screenshot: 'only-on-failure', trace: 'retain-on-failure' },
  webServer: { command: 'node ../../scripts/dev/e2e-server.mjs', url: 'http://127.0.0.1:1420', timeout: 30000, reuseExistingServer: false },
});
