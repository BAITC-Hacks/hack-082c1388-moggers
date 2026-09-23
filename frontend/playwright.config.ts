import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 30000,
  use: {
    baseURL: 'http://127.0.0.1:8000',
    browserName: 'chromium',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  webServer: {
    command: '../.venv/bin/python -m uvicorn moneygraph.api:app --host 127.0.0.1 --port 8000',
    url: 'http://127.0.0.1:8000/api/v1/dataset',
    reuseExistingServer: !process.env.CI,
  },
});
