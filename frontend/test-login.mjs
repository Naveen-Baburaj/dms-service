import { chromium } from 'playwright';

const OUT = 'C:\\Users\\admin\\AppData\\Local\\Temp';
const browser = await chromium.launch({ headless: true });

async function testLogin(email, password, label, expectedPath) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();

  // Go to login page
  await page.goto('http://localhost:3000/login', { waitUntil: 'networkidle' });
  await page.screenshot({ path: `${OUT}\\login-step1-form-${label}.png` });

  // Fill credentials
  await page.fill('#email', email);
  await page.fill('#password', password);
  await page.screenshot({ path: `${OUT}\\login-step2-filled-${label}.png` });

  // Submit
  await page.click('button[type="submit"]');

  // Wait for navigation
  try {
    await page.waitForURL(`**${expectedPath}**`, { timeout: 8000 });
    console.log(`✓ [${label}] Redirected to ${page.url()}`);
  } catch {
    console.log(`✗ [${label}] Still at ${page.url()} — expected ${expectedPath}`);
  }

  await page.waitForTimeout(2000);
  await page.screenshot({ path: `${OUT}\\login-step3-dashboard-${label}.png` });
  await ctx.close();
}

// Test all 4 roles
await testLogin('honda.manager@dms.local', 'honda123', 'honda', '/honda');
await testLogin('nexa.manager@dms.local', 'nexa123', 'nexa', '/nexa');
await testLogin('jaguar.manager@dms.local', 'jaguar123', 'jaguar', '/jaguar');
await testLogin('admin@dms.local', 'admin123', 'admin', '/admin');

// Test wrong password
{
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  await page.goto('http://localhost:3000/login', { waitUntil: 'networkidle' });
  await page.fill('#email', 'honda.manager@dms.local');
  await page.fill('#password', 'wrongpassword');
  await page.click('button[type="submit"]');
  await page.waitForTimeout(2000);
  const errorVisible = await page.locator('.text-red-400').isVisible();
  console.log(`${errorVisible ? '✓' : '✗'} Wrong password shows error message`);
  await page.screenshot({ path: `${OUT}\\login-step3-dashboard-error.png` });
  await ctx.close();
}

await browser.close();
console.log('\nAll tests complete.');
