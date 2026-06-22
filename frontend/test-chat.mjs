import { chromium } from 'playwright';

const JWT = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJob25kYS5tYW5hZ2VyQGRtcy5sb2NhbCIsImVtYWlsIjoiaG9uZGEubWFuYWdlckBkbXMubG9jYWwiLCJmdWxsX25hbWUiOiJSYWh1bCBTaGFybWEiLCJyb2xlIjoiaG9uZGFfbWFuYWdlciIsImNvbXBhbnkiOiJIb25kYSIsImNvbXBhbnlfaWQiOiJIT05EQS0wMDAwMSIsImlhdCI6MTc4MDAwMDAwMCwiZXhwIjoxNzk5OTk5OTk5fQ.mock_sig';
const user = { id:'u1', email:'honda.manager@dms.local', full_name:'Rahul Sharma', role:'honda_manager', company:'Honda', company_id:'HONDA-00001', is_active:true };
const authJson = JSON.stringify({ state: { user, tokens: { access_token: JWT, refresh_token:'r', expires_in:28800, token_type:'Bearer' }, isAuthenticated:true, isLoading:false, _hasHydrated:true }, version:0 });

const OUT = 'C:\\Users\\admin\\AppData\\Local\\Temp';
const browser = await chromium.launch({ headless: true });

async function shot(url, file, extraWait = 2000) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await ctx.addInitScript(({ authJson, jwt }) => {
    Storage.prototype.getItem = (function(orig) {
      return function(key) {
        if (key === 'dms-auth') return authJson;
        if (key === 'dms_access_token') return jwt;
        return orig.call(this, key);
      };
    })(Storage.prototype.getItem);
  }, { authJson, jwt: JWT });
  await ctx.addCookies([{ name:'dms_access_token', value:JWT, domain:'localhost', path:'/', expires: Math.floor(Date.now()/1000)+86400*7 }]);
  const page = await ctx.newPage();
  await page.goto(url, { waitUntil:'networkidle', timeout:25000 });
  await page.waitForTimeout(extraWait);
  await page.screenshot({ path: `${OUT}\\${file}` });
  await ctx.close();
  console.log(`✓ ${file}`);
}

// 1. Chat page - empty/welcome state
await shot('http://localhost:3000/chat', 'chat-01-welcome.png');

// 2. Honda dashboard showing the floating AI button + updated sidebar
await shot('http://localhost:3000/honda', 'chat-02-dashboard-float.png');

// 3. Chat page - simulate a conversation by clicking a suggested prompt
{
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await ctx.addInitScript(({ authJson, jwt }) => {
    Storage.prototype.getItem = (function(orig) {
      return function(key) {
        if (key === 'dms-auth') return authJson;
        if (key === 'dms_access_token') return jwt;
        return orig.call(this, key);
      };
    })(Storage.prototype.getItem);
  }, { authJson, jwt: JWT });
  await ctx.addCookies([{ name:'dms_access_token', value:JWT, domain:'localhost', path:'/', expires: Math.floor(Date.now()/1000)+86400*7 }]);
  const page = await ctx.newPage();
  await page.goto('http://localhost:3000/chat', { waitUntil:'networkidle', timeout:25000 });
  await page.waitForTimeout(1500);

  // Click "Summarize today's sales performance" suggestion
  const btns = page.locator('button:has(svg)').filter({ hasText: /sales/i });
  const allBtns = page.locator('button');
  const count = await allBtns.count();
  // Click the first suggestion card
  await page.locator('button', { hasText: "Summarize today's sales performance" }).click();
  await page.waitForTimeout(3000); // wait for AI typing + response
  await page.screenshot({ path: `${OUT}\\chat-03-conversation.png` });
  await ctx.close();
  console.log('✓ chat-03-conversation.png');
}

await browser.close();
