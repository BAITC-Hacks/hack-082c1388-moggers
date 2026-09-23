import { defineConfig } from '@playwright/test';
import { fileURLToPath } from 'node:url';

const python = fileURLToPath(
  new URL(
    process.platform === 'win32' ? '../.venv/Scripts/python.exe' : '../.venv/bin/python',
    import.meta.url,
  ),
);

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
    command: `"${python}" -m uvicorn moneygraph.api:app --host 127.0.0.1 --port 8000`,
    url: 'http://127.0.0.1:8000/api/v1/dataset',
    reuseExistingServer: !process.env.CI,
  },
});
