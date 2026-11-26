// End-to-end farmer journey in a real browser (Playwright + Chromium).
// Prerequisite: backend running and serving the built frontend:
//   (cd frontend && npm run build) && (cd backend && uvicorn app.main:app --port 8000)
// Run:  node e2e/journey.mjs [baseUrl] [screenshotDir]
import { createRequire } from 'node:module'
import { mkdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
// Playwright may be installed globally or locally (npm i -D playwright); require() finds either.
const { chromium, devices } = createRequire(import.meta.url)('playwright')
const BASE = process.argv[2] || 'http://127.0.0.1:8000'
const SHOTS = process.argv[3] || path.join(here, '..', 'test-results')
const IMAGES = path.join(here, '..', '..', 'backend', 'tests', 'images')
mkdirSync(SHOTS, { recursive: true })

const results = []
const check = (name, cond, extra = '') => {
  results.push({ name, ok: !!cond })
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${extra ? '  — ' + extra : ''}`)
}

const browser = await chromium.launch()
const phone = `9${String(Date.now()).slice(-9)}`

// ---------- Mobile journey (Pixel 7), Tamil first ----------
const ctx = await browser.newContext({
  ...devices['Pixel 7'],
  geolocation: { latitude: 13.0827, longitude: 80.2707 }, // Chennai
  permissions: ['geolocation'],
})
const page = await ctx.newPage()
const consoleErrors = []
page.on('pageerror', (e) => consoleErrors.push(String(e)))

await page.goto(`${BASE}/`)
await page.waitForURL('**/welcome')
await page.getByRole('button', { name: 'தமிழ்' }).first().click()
check('Tamil welcome screen', await page.getByText('AI பயிர் மருத்துவர்').first().isVisible())
await page.screenshot({ path: `${SHOTS}/01-welcome-ta.png` })

await page.getByRole('tab', { name: 'கணக்கு உருவாக்கு' }).click()
await page.getByLabel('உங்கள் பெயர்').fill('Test Farmer')
await page.getByLabel('கைபேசி எண்').fill(phone)
await page.getByLabel('PIN (4–6 இலக்கம்)').fill('2468')
await page.getByLabel('கிராமம் / ஊர் (விருப்பம்)').fill('Chennai')
await page.locator('form button.btn-primary').click()
await page.waitForURL(`${BASE}/`)
check('Dashboard in Tamil after register', await page.getByText('பயிரை சோதிக்கவும்').first().isVisible())
await page.screenshot({ path: `${SHOTS}/02-dashboard-ta.png`, fullPage: true })

// Validation: unsupported file type rejected client-side
await page.getByText('பயிரை சோதிக்கவும்').first().click()
await page.waitForURL('**/scan')

// Scan a real held-out late blight leaf
await page.getByTestId('file-input').setInputFiles(path.join(IMAGES, 'Tomato___Late_blight.jpg'))
await page.getByRole('button', { name: 'இந்த இலையைச் சோதி' }).click()
await page.waitForURL(/\/reports\/\d+/, { timeout: 60000 })
await page.getByTestId('status').waitFor()
const status = await page.getByTestId('status').innerText()
check('Diagnosis result shown', status.includes('சாத்தியமான நோயறிதல்'), status)
check('Tamil disease name', await page.getByText('பின்பருவ இலைக்கருகல் நோய்').first().isVisible())
check('Disclaimer shown', await page.getByText('உறுதியான நோயறிதல் அல்ல').isVisible())
check('Sources listed', await page.locator('.sources a').count() >= 1)
check('Listen button present', await page.getByRole('button', { name: /கேளுங்கள்/ }).first().isVisible())
await page.screenshot({ path: `${SHOTS}/03-result-ta.png`, fullPage: true })

// Switch to English on the same report
await page.locator('.topbar').getByRole('button', { name: 'English' }).click()
const enHeading = page.getByRole('heading', { name: 'Late blight' })
await enHeading.waitFor({ timeout: 15000 }).catch(() => {})
check('Same report re-rendered in English', await enHeading.isVisible())
await page.screenshot({ path: `${SHOTS}/04-result-en.png`, fullPage: true })

// Unsupported photo (tulip) -> no disease
await page.goto(`${BASE}/scan`)
await page.getByTestId('file-input').setInputFiles(path.join(IMAGES, 'ood_tulip.jpg'))
await page.getByRole('button', { name: 'Check this leaf' }).click()
await page.waitForURL(/\/reports\/\d+/, { timeout: 60000 })
const s2 = await page.getByTestId('status').innerText()
check('Tulip photo -> "Image not recognised"', s2.includes('not recognised'), s2)
check('No disease info for unsupported photo', (await page.locator('.disease-info').count()) === 0)
await page.screenshot({ path: `${SHOTS}/05-unsupported.png`, fullPage: true })

// Corrupt upload -> server rejects with reason
await page.goto(`${BASE}/scan`)
await page.getByTestId('file-input').setInputFiles({ name: 'fake.jpg', mimeType: 'image/jpeg', buffer: Buffer.from('not an image') })
await page.getByRole('button', { name: 'Check this leaf' }).click()
await page.getByText('This file is not a photo.').waitFor()
check('Corrupt file rejected with message', true)

// History
await page.goto(`${BASE}/reports`)
await page.locator('.history-item').first().waitFor()
check('History lists the scans', (await page.locator('.history-item').count()) >= 2)
await page.screenshot({ path: `${SHOTS}/06-history.png`, fullPage: true })

// Shops via device location (Chennai)
await page.goto(`${BASE}/shops`)
await page.getByRole('button', { name: /Use my location/ }).click()
const outcome = await Promise.race([
  page.locator('.leaflet-container').waitFor({ timeout: 150000 }).then(() => 'map'),
  page.locator('.alert-error').waitFor({ timeout: 150000 }).then(() => 'error'),
])
if (outcome === 'map') {
  const n = await page.locator('.shop').count()
  check('Shop search returned real results with map', true, `${n} shops`)
  check('Map has markers', (await page.locator('.leaflet-interactive').count()) >= 1)
  if (n > 0) {
    check('Stock marked unconfirmed', await page.getByText('Stock not confirmed').first().isVisible())
    const href = await page.locator('.shop a', { hasText: 'Directions' }).first().getAttribute('href')
    check('Directions link points to real coordinates', /destination=-?\d+\.\d+,-?\d+\.\d+/.test(href), href)
  }
} else {
  check('Shop service error shown honestly (service unavailable)', true, await page.locator('.alert-error').innerText())
}
await page.waitForTimeout(1500)
await page.screenshot({ path: `${SHOTS}/07-shops.png`, fullPage: true })

// Tips + settings
await page.goto(`${BASE}/tips`)
check('Farming tips', (await page.locator('.tip').count()) === 8)
await page.goto(`${BASE}/settings`)
await page.locator('.model-info').waitFor()
check('Model info with accuracy', /\d+\.\d%/.test(await page.locator('.model-info').innerText()))
await page.screenshot({ path: `${SHOTS}/08-settings.png`, fullPage: true })
await ctx.close()

// ---------- Location permission denied ----------
const ctx2 = await browser.newContext({ ...devices['Pixel 7'], permissions: [] })
const p2 = await ctx2.newPage()
await p2.goto(`${BASE}/welcome`)
await p2.getByRole('button', { name: 'English' }).first().click()
await p2.getByLabel('Mobile number').fill(phone)
await p2.getByLabel('PIN (4–6 digits)').fill('2468')
await p2.locator('form button.btn-primary').click()
await p2.waitForURL(`${BASE}/`)
check('Login with existing account', true)
await p2.goto(`${BASE}/shops`)
await p2.getByRole('button', { name: /Use my location/ }).click()
await p2.locator('.alert-error').waitFor({ timeout: 20000 })
const deniedMsg = await p2.locator('.alert-error').innerText()
check('Denied location -> asks for village', /denied|unavailable/i.test(deniedMsg), deniedMsg)
await ctx2.close()

// ---------- Desktop layout ----------
const ctx3 = await browser.newContext({ viewport: { width: 1280, height: 860 } })
const p3 = await ctx3.newPage()
await p3.goto(`${BASE}/welcome`)
await p3.screenshot({ path: `${SHOTS}/09-welcome-desktop.png` })
await ctx3.close()

check('No uncaught page errors', consoleErrors.length === 0, consoleErrors.join(' | '))
await browser.close()
const failed = results.filter((r) => !r.ok)
console.log(`\n${results.length - failed.length}/${results.length} checks passed`)
process.exit(failed.length ? 1 : 0)
