import { NextRequest, NextResponse } from 'next/server';

const INTERNAL_BACKEND_ORIGIN = (
  process.env.DMS_INTERNAL_API_URL ?? 'http://dms.localhost:8000'
).replace(/\/$/, '');
const FRAPPE_SITE_NAME = process.env.DMS_FRAPPE_SITE ?? 'dms.localhost';

const HOP_BY_HOP_HEADERS = new Set([
  'connection',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailer',
  'transfer-encoding',
  'upgrade',
  'host',
  'content-length',
]);

function buildBackendHeaders(request: NextRequest): Headers {
  const headers = new Headers();

  request.headers.forEach((value, key) => {
    if (!HOP_BY_HOP_HEADERS.has(key.toLowerCase())) {
      headers.set(key, value);
    }
  });

  headers.set('X-Frappe-Site-Name', FRAPPE_SITE_NAME);
  headers.set('X-Forwarded-Proto', request.nextUrl.protocol.replace(':', ''));
  headers.set('X-Forwarded-Host', request.nextUrl.host);

  return headers;
}

function browserCookie(cookie: string): string {
  // The browser talks only to the public frontend. Never leak a private backend
  // hostname (or the internal Frappe site name) into a forwarded cookie domain.
  return cookie.replace(/;\s*Domain=[^;]*/gi, '');
}

async function proxy(request: NextRequest): Promise<NextResponse> {
  const path = request.nextUrl.pathname.replace(/^\/api/, '');
  const target = `${INTERNAL_BACKEND_ORIGIN}/api${path}${request.nextUrl.search}`;
  const method = request.method.toUpperCase();
  const body = ['GET', 'HEAD'].includes(method)
    ? undefined
    : await request.arrayBuffer();

  const upstream = await fetch(target, {
    method,
    headers: buildBackendHeaders(request),
    body,
    redirect: 'manual',
    cache: 'no-store',
  });

  const responseHeaders = new Headers();
  upstream.headers.forEach((value, key) => {
    const normalized = key.toLowerCase();
    if (!HOP_BY_HOP_HEADERS.has(normalized) && normalized !== 'set-cookie') {
      responseHeaders.append(key, value);
    }
  });

  const getSetCookie = (
    upstream.headers as Headers & { getSetCookie?: () => string[] }
  ).getSetCookie;

  if (typeof getSetCookie === 'function') {
    for (const cookie of getSetCookie.call(upstream.headers)) {
      responseHeaders.append('set-cookie', browserCookie(cookie));
    }
  } else {
    const setCookie = upstream.headers.get('set-cookie');
    if (setCookie) {
      responseHeaders.append('set-cookie', browserCookie(setCookie));
    }
  }

  return new NextResponse(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const OPTIONS = proxy;
export const HEAD = proxy;
