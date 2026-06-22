import { chromium } from 'playwright';

const OUT = 'C:\\Users\\admin\\AppData\\Local\\Temp';
const browser = await chromium.launch({ headless: true });

function makeAuth(jwt, user) {
  return JSON.stringify({
    state: { user, tokens: { access_token: jwt, refresh_token: 'r', expires_in: 28800, token_type: 'Bearer' }, isAuthenticated: true, isLoading: false, _hasHydrated: true },
    version: 0,
  });
}

async function shot(url, file, jwt, user, extraWait = 2000) {
  const authJson = makeAuth(jwt, user);
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await ctx.addInitScript(({ authJson, jwt }) => {
    Storage.prototype.getItem = (function (o) {
      return function (k) {
        if (k === 'dms-auth') return authJson;
        if (k === 'dms_access_token') return jwt;
        return o.call(this, k);
      };
    })(Storage.prototype.getItem);
  }, { authJson, jwt });
  await ctx.addCookies([{ name: 'dms_access_token', value: jwt, domain: 'localhost', path: '/', expires: Math.floor(Date.now() / 1000) + 86400 * 7 }]);
  const page = await ctx.newPage();
  await page.goto(url, { waitUntil: 'networkidle', timeout: 25000 });
  await page.waitForTimeout(extraWait);
  await page.screenshot({ path: `${OUT}\\${file}` });
  await ctx.close();
  console.log(`✓ ${file}`);
}

// JWTs
const HONDA_JWT = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJob25kYS5tYW5hZ2VyQGRtcy5sb2NhbCIsImVtYWlsIjoiaG9uZGEubWFuYWdlckBkbXMubG9jYWwiLCJmdWxsX25hbWUiOiJSYWh1bCBTaGFybWEiLCJyb2xlIjoiaG9uZGFfbWFuYWdlciIsImNvbXBhbnkiOiJIb25kYSIsImNvbXBhbnlfaWQiOiJIT05EQS0wMDAwMSIsImlhdCI6MTc4MDAwMDAwMCwiZXhwIjoxNzk5OTk5OTk5fQ.mock_sig';
const NEXA_JWT  = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJuZXhhLm1hbmFnZXJAZG1zLmxvY2FsIiwiZW1haWwiOiJuZXhhLm1hbmFnZXJAZG1zLmxvY2FsIiwiZnVsbF9uYW1lIjoiUHJpeWEgTWVodGEiLCJyb2xlIjoibmV4YV9tYW5hZ2VyIiwiY29tcGFueSI6Ik5FWEEiLCJjb21wYW55X2lkIjoiTkVYQS0wMDAwMSIsImlhdCI6MTc4MDAwMDAwMCwiZXhwIjoxNzk5OTk5OTk5fQ.mock_sig';
const JAG_JWT   = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJqYWd1YXIubWFuYWdlckBkbXMubG9jYWwiLCJlbWFpbCI6ImphZ3Vhci5tYW5hZ2VyQGRtcy5sb2NhbCIsImZ1bGxfbmFtZSI6IkFyanVuIEthcG9vciIsInJvbGUiOiJqYWd1YXJfbWFuYWdlciIsImNvbXBhbnkiOiJKYWd1YXIiLCJjb21wYW55X2lkIjoiSkFHLTAwMDAxIiwiaWF0IjoxNzgwMDAwMDAwLCJleHAiOjE3OTk5OTk5OTl9.mock_sig';
const ADMIN_JWT = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbkBkbXMubG9jYWwiLCJlbWFpbCI6ImFkbWluQGRtcy5sb2NhbCIsImZ1bGxfbmFtZSI6IkFkbWluIFVzZXIiLCJyb2xlIjoiZ3JvdXBfYWRtaW4iLCJjb21wYW55IjoiR3JvdXAiLCJjb21wYW55X2lkIjoiR1JPVVAtMDAwMDEiLCJpYXQiOjE3ODAwMDAwMDAsImV4cCI6MTc5OTk5OTk5OX0.mock_sig';

const hondaUser = { id:'u1', email:'honda.manager@dms.local', full_name:'Rahul Sharma',  role:'honda_manager',  company:'Honda',  company_id:'HONDA-00001', is_active:true };
const nexaUser  = { id:'u2', email:'nexa.manager@dms.local',  full_name:'Priya Mehta',   role:'nexa_manager',   company:'NEXA',   company_id:'NEXA-00001',  is_active:true };
const jagUser   = { id:'u3', email:'jaguar.manager@dms.local',full_name:'Arjun Kapoor',  role:'jaguar_manager', company:'Jaguar', company_id:'JAG-00001',   is_active:true };
const adminUser = { id:'u4', email:'admin@dms.local',         full_name:'Admin User',    role:'group_admin',    company:'Group',  company_id:'GROUP-00001', is_active:true };

// Login page (no auth)
{
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  await page.goto('http://localhost:3000/login', { waitUntil: 'networkidle' });
  await page.screenshot({ path: `${OUT}\\run-01-login.png` });
  await ctx.close();
  console.log('✓ run-01-login.png');
}

await shot('http://localhost:3000/honda',       'run-02-honda-dashboard.png',   HONDA_JWT, hondaUser);
await shot('http://localhost:3000/nexa',        'run-03-nexa-dashboard.png',    NEXA_JWT,  nexaUser);
await shot('http://localhost:3000/jaguar',      'run-04-jaguar-dashboard.png',  JAG_JWT,   jagUser);
await shot('http://localhost:3000/admin',       'run-05-admin-dashboard.png',   ADMIN_JWT, adminUser);
await shot('http://localhost:3000/leads',       'run-06-leads.png',             HONDA_JWT, hondaUser);
await shot('http://localhost:3000/customers',   'run-07-customers.png',         HONDA_JWT, hondaUser);
await shot('http://localhost:3000/sales',       'run-08-sales.png',             HONDA_JWT, hondaUser);
await shot('http://localhost:3000/bookings',    'run-09-bookings.png',          HONDA_JWT, hondaUser);
await shot('http://localhost:3000/test-drives', 'run-10-test-drives.png',       HONDA_JWT, hondaUser);
await shot('http://localhost:3000/service',     'run-11-service.png',           HONDA_JWT, hondaUser);
await shot('http://localhost:3000/invoices',    'run-12-invoices.png',          HONDA_JWT, hondaUser);
await shot('http://localhost:3000/reports',     'run-13-reports.png',           HONDA_JWT, hondaUser);
await shot('http://localhost:3000/settings',    'run-14-settings.png',          HONDA_JWT, hondaUser);
await shot('http://localhost:3000/chat',        'run-15-chat.png',              HONDA_JWT, hondaUser);
await shot('http://localhost:3000/admin/companies',    'run-16-admin-companies.png',   ADMIN_JWT, adminUser);
await shot('http://localhost:3000/admin/users',        'run-17-admin-users.png',       ADMIN_JWT, adminUser);
await shot('http://localhost:3000/admin/analytics',    'run-18-admin-analytics.png',   ADMIN_JWT, adminUser);
await shot('http://localhost:3000/admin/system',       'run-19-admin-system.png',      ADMIN_JWT, adminUser);

await browser.close();
console.log('\n✓ All screenshots done');
