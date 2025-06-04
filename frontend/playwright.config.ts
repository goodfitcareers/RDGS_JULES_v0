import { defineConfig, devices } from '@playwright/test';
import path from 'path';

// Define the path to the frontend directory relative to this config file
const frontendDir = __dirname; // This config is in frontend/, so __dirname is frontend/

export default defineConfig({
  // Look for test files in the "e2e" directory, relative to the configuration file.
  testDir: path.join(frontendDir, 'e2e'),

  // Each test is given 30 seconds.
  timeout: 30 * 1000,

  // Forbid test.only on CI
  forbidOnly: !!process.env.CI,

  // Retry on CI only.
  retries: process.env.CI ? 2 : 0,

  // Limit the number of workers on CI, use default locally
  workers: process.env.CI ? 1 : undefined,

  // Reporter to use
  reporter: 'html',

  use: {
    // Base URL to use in actions like `await page.goto('/')`.
    baseURL: 'http://localhost:3000', // Vite's default port

    // Collect trace when retrying the failed test.
    trace: 'on-first-retry',
  },

  // Configure projects for major browsers.
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    // {
    //   name: 'firefox',
    //   use: { ...devices['Desktop Firefox'] },
    // },
    // {
    //   name: 'webkit',
    //   use: { ...devices['Desktop Safari'] },
    // },
  ],

  // Run your local dev server before starting the tests.
  webServer: {
    // Command to start the dev server.
    // It's crucial that this command correctly starts your frontend application.
    // Assuming pnpm is available and you're running tests from the monorepo root
    // or that pnpm can find the frontend workspace.
    // The CWD for this command is the directory where `playwright test` is run.
    // If running `pnpm exec playwright test -c frontend/playwright.config.ts` from root,
    // then CWD is root.
    command: 'pnpm --filter frontend dev --port 3000 --host',
    url: 'http://localhost:3000', // URL to wait for before starting tests
    reuseExistingServer: !process.env.CI, // Reuse server locally, start new on CI
    cwd: path.resolve(frontendDir, '..'), // Run pnpm from the monorepo root directory
    timeout: 120 * 1000, // Increase timeout for web server to start
    // stdout: 'pipe', // Capture stdout
    // stderr: 'pipe', // Capture stderr
  },
});
