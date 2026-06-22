import { chromium } from 'playwright';

const JWT = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmdWxsX25hbWUiOiJSYWh1bCBTaGFybWEiLCJjb21wYW55X2lkIjoiSE9OREEtMDAwMDEiLCJleHAiOjE3ODI0OTMyNDUsImNvbXBhbnkiOiJIb25kYSIsImlhdCI6MTc4MTg4ODQ0NSwic3ViIjoiaG9uZGEubWFuYWdlckBleGFtcGxlLmNvbSIsInJvbGUiOiJob25kYV9tYW5hZ2VyIiwiZW1haWwiOiJob25kYS5tYW5hZ2VyQGV4YW1wbGUuY29tIn0.mock_signature';
const ADMIN_JWT = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmdWxsX25hbWUiOiJBZG1pbiBVc2VyIiwiY29tcGFueV9pZCI6Ikdyb3VwIiwiZXhwIjoxNzgyNDkzMjQ1LCJjb21wYW55IjoiR3JvdXAiLCJpYXQiOjE3ODE4ODg0NDUsInN1YiI6ImFkbWluQGV4YW1wbGUuY29tIiwicm9sZSI6Imdyb3VwX2FkbWluIiwiZW1haWwiOiJhZG1pbkBleGFtcGxlLmNvbSJ9.mock';

const hondaUser = { id: 'honda.manager@example.com', email: 'honda.manager@example.com', full_name: 'Rahul Sharma', role: 'honda_manager', company: 'Honda', company_id: 'HONDA-00001', is_active: true };
const adminUser = { id: 'admin@example.com', email: 'admin@example.com', full_name: 'Admin User', role: 'group_admin', company: 'Group', company_id: 'Group', is_active: true };

function makeZustandState(jwt, user) {
  return JSON.stringify({
    state: { user, tokens: { access_token: jwt, refresh_token: 'r', expires_in: 28800, token_type: 'Bearer' }, isAuthenticated: true, isLoading: false },
    version: 0,
  });
}

const browser = await chromium.launch({ headless: true });
const OUT = 'C:\\Users\\admin\\AppData\\Local\\Temp';

async function shot(url, outFile, jwt, user) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });

  // addInitScript runs BEFORE any page script — Zustand persist picks it up on hydration
  const authJson = makeZustandState(jwt, user);
  await ctx.addInitScript(({ authJson, jwt }) => {
    Object.defineProperty(window, '_dmsPreloadAuth', { value: { authJson, jwt } });
    const orig = Storage.prototype.getItem;
    Storage.prototype.getItem = function(key) {
      if (key === 'dms-auth') return authJson;
      if (key === 'dms_access_token') return jwt;
      return orig.call(this, key);
    };
  }, { authJson, jwt });

  // Cookie for Next.js middleware
  await ctx.addCookies([{
    name: 'dms_access_token', value: jwt, domain: 'localhost', path: '/',
    expires: Math.floor(Date.now() / 1000) + 86400 * 7,
  }]);

  const page = await ctx.newPage();
  await page.goto(url, { waitUntil: 'networkidle', timeout: 25000 });
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `${OUT}\\${outFile}` });
  await ctx.close();
  console.log(`✓ ${outFile}`);
}

// 1. Login page (no auth needed)
{
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  await page.goto('http://localhost:3000/login', { waitUntil: 'networkidle' });
  await page.screenshot({ path: `${OUT}\\dms-01-login.png` });
  await ctx.close();
  console.log('✓ dms-01-login.png');
}

await shot('http://localhost:3000/honda', 'dms-02-honda.png', JWT, hondaUser);
await shot('http://localhost:3000/leads', 'dms-03-leads.png', JWT, hondaUser);
await shot('http://localhost:3000/admin', 'dms-04-admin.png', ADMIN_JWT, adminUser);

await browser.close();
console.log('All done!');
