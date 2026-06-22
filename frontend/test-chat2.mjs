import { chromium } from 'playwright';

const JWT = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJob25kYS5tYW5hZ2VyQGRtcy5sb2NhbCIsImVtYWlsIjoiaG9uZGEubWFuYWdlckBkbXMubG9jYWwiLCJmdWxsX25hbWUiOiJSYWh1bCBTaGFybWEiLCJyb2xlIjoiaG9uZGFfbWFuYWdlciIsImNvbXBhbnkiOiJIb25kYSIsImNvbXBhbnlfaWQiOiJIT05EQS0wMDAwMSIsImlhdCI6MTc4MDAwMDAwMCwiZXhwIjoxNzk5OTk5OTk5fQ.mock_sig';
const user = { id:'u1', email:'honda.manager@dms.local', full_name:'Rahul Sharma', role:'honda_manager', company:'Honda', company_id:'HONDA-00001', is_active:true };
const authJson = JSON.stringify({ state: { user, tokens: { access_token: JWT, refresh_token:'r', expires_in:28800, token_type:'Bearer' }, isAuthenticated:true, isLoading:false, _hasHydrated:true }, version:0 });

const ADMIN_JWT = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbkBkbXMubG9jYWwiLCJlbWFpbCI6ImFkbWluQGRtcy5sb2NhbCIsImZ1bGxfbmFtZSI6IkFkbWluIFVzZXIiLCJyb2xlIjoiZ3JvdXBfYWRtaW4iLCJjb21wYW55IjoiR3JvdXAiLCJjb21wYW55X2lkIjoiR1JPVVAtMDAwMDEiLCJpYXQiOjE3ODAwMDAwMDAsImV4cCI6MTc5OTk5OTk5OX0.mock_sig';
const adminUser = { id:'u4', email:'admin@dms.local', full_name:'Admin User', role:'group_admin', company:'Group', company_id:'GROUP-00001', is_active:true };
const adminAuthJson = JSON.stringify({ state: { user: adminUser, tokens: { access_token: ADMIN_JWT, refresh_token:'r', expires_in:28800, token_type:'Bearer' }, isAuthenticated:true, isLoading:false, _hasHydrated:true }, version:0 });

const OUT = 'C:\\Users\\admin\\AppData\\Local\\Temp';
const browser = await chromium.launch({ headless: true });

async function makeCtx(jwt, json) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await ctx.addInitScript(({ authJson, jwt }) => {
    Storage.prototype.getItem = (function(orig) {
      return function(key) {
        if (key === 'dms-auth') return authJson;
        if (key === 'dms_access_token') return jwt;
        return orig.call(this, key);
      };
    })(Storage.prototype.getItem);
  }, { authJson: json, jwt });
  await ctx.addCookies([{ name:'dms_access_token', value:jwt, domain:'localhost', path:'/', expires: Math.floor(Date.now()/1000)+86400*7 }]);
  return ctx;
}

// 1. Welcome screen (Honda)
{
  const ctx = await makeCtx(JWT, authJson);
  const page = await ctx.newPage();
  await page.goto('http://localhost:3000/chat', { waitUntil:'networkidle', timeout:25000 });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${OUT}\\chat2-01-welcome.png` });
  await ctx.close();
  console.log('✓ chat2-01-welcome.png');
}

// 2. Click "What was the sales in the last 5 months?" and wait for AI response
{
  const ctx = await makeCtx(JWT, authJson);
  const page = await ctx.newPage();
  await page.goto('http://localhost:3000/chat', { waitUntil:'networkidle', timeout:25000 });
  await page.waitForTimeout(1500);
  // Click the first suggested prompt
  await page.locator('button', { hasText: 'What was the sales in the last 5 months?' }).click();
  // Wait for the response (real API call — up to 10s)
  await page.waitForSelector('text=Total sales', { timeout: 10000 }).catch(() => {});
  await page.waitForTimeout(1000);
  await page.screenshot({ path: `${OUT}\\chat2-02-sales-response.png` });
  await ctx.close();
  console.log('✓ chat2-02-sales-response.png');
}

// 3. Inventory query
{
  const ctx = await makeCtx(JWT, authJson);
  const page = await ctx.newPage();
  await page.goto('http://localhost:3000/chat', { waitUntil:'networkidle', timeout:25000 });
  await page.waitForTimeout(1000);
  // Type inventory question directly
  await page.locator('textarea').fill('What is the current inventory stock?');
  await page.locator('textarea').press('Enter');
  await page.waitForSelector('text=inventory', { timeout: 10000 }).catch(() => {});
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${OUT}\\chat2-03-inventory.png` });
  await ctx.close();
  console.log('✓ chat2-03-inventory.png');
}

// 4. Admin - tenant comparison
{
  const ctx = await makeCtx(ADMIN_JWT, adminAuthJson);
  const page = await ctx.newPage();
  await page.goto('http://localhost:3000/chat', { waitUntil:'networkidle', timeout:25000 });
  await page.waitForTimeout(1000);
  await page.locator('button', { hasText: 'Compare sales across all tenants' }).click();
  await page.waitForSelector('text=sales', { timeout: 10000 }).catch(() => {});
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${OUT}\\chat2-04-admin-comparison.png` });
  await ctx.close();
  console.log('✓ chat2-04-admin-comparison.png');
}

await browser.close();
console.log('\n✓ All AI chat screenshots done');
