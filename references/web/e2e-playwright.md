# Web End-to-End Proof with Playwright — Setup and Examples

The rule is `rules/web-testing.md`. This file shows how to set it up in a web project and gives copyable examples. The examples assume a Vite + React + TypeScript project with npm; change the dev server command for another tool.

---

## 1. Install

```bash
npm install --save-dev @playwright/test dotenv
npx playwright install chromium
```

Add to `.gitignore`:

```
.env
e2e/.auth/
build/
```

Commit `.env.example` with the variable names from the rule and empty values:

```
E2E_BASE_URL=
E2E_USERNAME=
E2E_PASSWORD=
E2E_OTP=
```

Add the script to `package.json`:

```json
"scripts": {
  "e2e": "playwright test"
}
```

---

## 2. Config

`playwright.config.ts` at the repo root:

```ts
import { defineConfig, devices } from '@playwright/test';
import dotenv from 'dotenv';

dotenv.config({ quiet: true });

const baseURL = process.env.E2E_BASE_URL || 'http://localhost:5173';
const port = new URL(baseURL).port;
if (!port) throw new Error('E2E_BASE_URL must include the dev server port, for example http://localhost:5173.');
const outputRoot = 'build/e2e/web';

export default defineConfig({
  testDir: 'e2e',
  outputDir: `${outputRoot}/test-results`,
  fullyParallel: false,
  retries: 0,
  reporter: [
    ['list'],
    ['html', { outputFolder: `${outputRoot}/report`, open: 'never' }],
    ['junit', { outputFile: `${outputRoot}/junit.xml` }],
  ],
  use: {
    baseURL,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    { name: 'setup', testMatch: /auth\.setup\.ts/ },
    {
      name: 'chromium',
      testDir: 'e2e/flows',
      dependencies: ['setup'],
      use: { ...devices['Desktop Chrome'], storageState: 'e2e/.auth/state.json' },
    },
  ],
  webServer: {
    command: `npm run dev -- --port ${port} --strictPort`,
    url: baseURL,
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
```

- `retries: 0` keeps a flaky flow visible. The runner reruns a failed flow by hand at most once and reports it as flaky when the rerun passes unchanged.
- `trace: 'retain-on-failure'` keeps the trace only for failing runs, which is what the pull request needs.
- `webServer` starts the dev server of the checkout the flows run in, so the flows test the code on the branch. `reuseExistingServer: false` and `--strictPort` make the run fail when the port is already taken, instead of testing a server started from another checkout or moving to another port. The port stays fixed because the saved sign-in belongs to one address (origin). Stop your own `npm run dev` before running the flows. When the flows should run against a deployed test environment instead, set `E2E_BASE_URL` to it and remove `webServer`.

---

## 3. Sign in once: `e2e/auth.setup.ts`

The setup project runs before the flows. It reuses the saved state when it is still signed in, and signs in only when it is not.

```ts
import { test as setup, expect } from '@playwright/test';
import fs from 'node:fs';

const statePath = 'e2e/.auth/state.json';

setup('sign in', async ({ browser }) => {
  if (fs.existsSync(statePath)) {
    const context = await browser.newContext({ storageState: statePath });
    const page = await context.newPage();
    await page.goto('/');
    const signedIn = await page
      .getByRole('navigation')
      .waitFor({ timeout: 10_000 })
      .then(() => true, () => false);
    await context.close();
    if (signedIn) return;
  }

  const username = process.env.E2E_USERNAME;
  const password = process.env.E2E_PASSWORD;
  const otp = process.env.E2E_OTP;
  if (!username || !password) {
    throw new Error('E2E_USERNAME or E2E_PASSWORD is not set. Create .env from .env.example.');
  }
  if (!otp) {
    throw new Error('No valid saved sign-in and no E2E_OTP. Run e2e/scripts/login.sh once, or set E2E_OTP in .env.');
  }

  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto('/login');
  await page.getByLabel('Email').fill(username);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.getByLabel('Code').fill(otp);
  await page.getByRole('button', { name: 'Verify' }).click();
  await expect(page.getByRole('navigation')).toBeVisible();
  await context.storageState({ path: statePath });
  await context.close();
});
```

Change the labels and the "signed in" check to the project's own screen. The error message never contains the values.

---

## 4. Sign in by hand: `e2e/scripts/login.sh`

For a test environment that sends a new one-time code each time (no fixed `E2E_OTP`). A person runs it once; the flows reuse the saved state until the session expires.

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
mkdir -p e2e/.auth
set -a; source .env; set +a
npx playwright open --save-storage=e2e/.auth/state.json "$E2E_BASE_URL/login"
```

Sign in in the window that opens, type the code, wait for the first page after sign-in, then close the window. Start the dev server first when `E2E_BASE_URL` points to it.

---

## 5. Run one flow: `e2e/scripts/run-flow.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
if [ $# -lt 1 ]; then
  echo "usage: e2e/scripts/run-flow.sh <flow> [playwright options]" >&2
  exit 2
fi
flow="$1"
shift
rm -rf "build/e2e/web/screenshots/${flow}"
npx playwright test "e2e/flows/${flow}.spec.ts" --project=chromium "$@"
```

Results land in `build/e2e/web/`: `junit.xml`, `report/index.html`, and per failing test a folder under `test-results/` with `trace.zip`, the failure screenshot and the video. Playwright empties `test-results/` at the start of every run, so copy a failing run's `trace.zip` elsewhere before the next run. Screenshots a flow takes itself land in `build/e2e/web/screenshots/<flow>/`, which the script empties before the run.

---

## 6. A flow and a subflow

`e2e/subflows/open-orders.ts`:

```ts
import { expect, type Page } from '@playwright/test';

export async function openOrders(page: Page) {
  await page.goto('/');
  await page.getByRole('link', { name: 'Orders' }).click();
  await expect(page.getByRole('heading', { name: 'Orders' })).toBeVisible();
}
```

`e2e/flows/orders-filter.spec.ts`:

```ts
import { test, expect } from '@playwright/test';
import { openOrders } from '../subflows/open-orders';

const screenshotDir = 'build/e2e/web/screenshots/orders-filter';

test('filter orders by status shows only matching rows', async ({ page }) => {
  await openOrders(page);
  await page.getByLabel('Status').selectOption('Paid');
  await expect(page.getByRole('row', { name: /Unpaid/ })).toHaveCount(0);
  await page.screenshot({ path: `${screenshotDir}/orders-filter-paid.png`, fullPage: true });
});
```

---

## 7. Before and after for a bug fix

1. Check out the default branch in its own folder, copy `.env` and `e2e/.auth/` next to it, and run the flow. It must fail or show the problem. Keep that run's `trace.zip` and screenshots as the "before".
2. Run the same flow on the fix branch with the same `.env`. Keep the screenshots as the "after".
3. If the old code passes the flow, the flow does not reproduce the problem yet. Change the flow before testing the fix.

---

## 8. Common mistakes

- Signing in inside a flow. Every flow then depends on the one-time code and is slow; use the setup project.
- `page.waitForTimeout(2000)` to wait for data. Wait for the element or the URL instead.
- Selecting `.btn-primary` or `div > span:nth-child(2)`. These break on any style change; select by role and name.
- Committing `e2e/.auth/state.json` or a `trace.zip`. Both hold session cookies.
- Running the dev server on another port than the one the saved state was made for. The browser keeps the sign-in per address, so the flows land on the sign-in page.
