/**
 * Playwright global setup — bypass setup wizard for E2E tests.
 *
 * Accepts the disclaimer and marks a database as installed so the
 * AuthGuard doesn't redirect to /setup.
 */

import * as fs from 'fs'
import * as path from 'path'

const BACKEND_URL = process.env.BACKEND_URL ?? 'http://localhost:8000'

export default async function globalSetup() {
  // Accept the disclaimer so needs_setup can be false
  const disclaimerResp = await fetch(`${BACKEND_URL}/api/setup/accept-disclaimer`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  })
  if (!disclaimerResp.ok) {
    console.warn(`[e2e-setup] Failed to accept disclaimer: ${disclaimerResp.status}`)
  }

  // Create a dummy standalone DB file so _has_any_databases() returns true.
  // The data_dir defaults to ~/.genomeinsight/data (or $GENOMEINSIGHT_DATA_DIR).
  const dataDir = process.env.GENOMEINSIGHT_DATA_DIR
    ?? path.join(process.env.HOME ?? '/tmp', '.genomeinsight', 'data')
  fs.mkdirSync(dataDir, { recursive: true })
  const dummyDb = path.join(dataDir, 'gnomad_af.db')
  if (!fs.existsSync(dummyDb)) {
    fs.writeFileSync(dummyDb, '')
  }
}
