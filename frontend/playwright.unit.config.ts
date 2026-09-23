import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  testMatch: 'graph.spec.ts',
  grep: /(cluster flows preserve|node view groups|progressive expansion preserves)/,
});
