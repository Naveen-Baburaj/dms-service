import { chromium } from 'playwright';

const JWT_HONDA = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJob25kYS5tYW5hZ2VyQGRtcy5sb2NhbCIsImVtYWlsIjoiaG9uZGEubWFuYWdlckBkbXMubG9jYWwiLCJmdWxsX25hbWUiOiJSYWh1bCBTaGFybWEiLCJyb2xlIjoiaG9uZGFfbWFuYWdlciIsImNvbXBhbnkiOiJIb25kYSIsImNvbXBhbnlfaWQiOiJIT05EQS0wMDAwMSIsImlhdCI6MTc4MDAwMDAwMCwiZXhwIjoxNzk5OTk5OTk5fQ.mock_sig';
const JWT_ADMIN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbkBkbXMubG9jYWwiLCJlbWFpbCI6ImFkbWluQGRtcy5sb2NhbCIsImZ1bGxfbmFtZSI6IkFkbWluIFVzZXIiLCJyb2xlIjoiZ3JvdXBfYWRtaW4iLCJjb21wYW55IjoiR3JvdXAiLCJjb21wYW55X2lkIjoiR1JPVVAtMDAwMDEiLCJpYXQiOjE3ODAwMDAwMDAsImV4cCI6MTc5OTk5OTk5OX0.mock_sig';

const hondaUser = { id:'u1', email:'honda.manager@dms.local', full_name:'Rahul Sharma', role:'honda_manager', company:'Honda', company_id:'HONDA-00001', is_active:true };
const adminUser = { id:'u4', email:'admin@dms.local', full_name:'Admin User', role:'group_admin', company:'Group', company_id:'GROUP-00001', is_active:true };

function makeAuth(jwt, user) {
  return JSON.stringify({ state: { user, tokens: { access_token: jwt, refresh_token:'r', expires_in:28800, token_type:'Bearer' }, isAuthenticated:true, isLoading:false, _hasHydrated:true }, version:0 });
}

const browser = await chromium.launch({ headless: true });
const OUT = 'C:\\Users\\admin\\AppData\\Local\\Temp';

async function shot(url, file, jwt, user) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const authJson = makeAuth(jwt, user);
  await ctx.addInitScript(({ authJson, jwt }) => {
    Storage.prototype.getItem = (function(orig) {
      return function(key) {
        if (key === 'dms-auth') return authJson;
        if (key === 'dms_access_token') return jwt;
        return orig.call(this, key);
      };
    })(Storage.prototype.getItem);
  }, { authJson, jwt });
  await ctx.addCookies([{ name:'dms_access_token', value:jwt, domain:'localhost', path:'/', expires: Math.floor(Date.now()/1000)+86400*7 }]);
  const page = await ctx.newPage();
  await page.goto(url, { waitUntil:'networkidle', timeout:20000 });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${OUT}\\${file}` });
  await ctx.close();
  console.log(`✓ ${file}`);
}

await shot('http://localhost:3000/settings', 'pg-settings.png', JWT_HONDA, hondaUser);
await shot('http://localhost:3000/bookings', 'pg-bookings.png', JWT_HONDA, hondaUser);
await shot('http://localhost:3000/admin/users', 'pg-admin-users.png', JWT_ADMIN, adminUser);
await shot('http://localhost:3000/admin/companies', 'pg-admin-companies.png', JWT_ADMIN, adminUser);
await shot('http://localhost:3000/admin/analytics', 'pg-admin-analytics.png', JWT_ADMIN, adminUser);
await shot('http://localhost:3000/admin/system', 'pg-admin-system.png', JWT_ADMIN, adminUser);

await browser.close();
