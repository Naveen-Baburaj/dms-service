import { NextResponse, type NextRequest } from 'next/server';

const PUBLIC_PATHS = ['/login', '/forgot-password'];

const PUBLIC_BACKEND_ORIGIN =
  process.env.NEXT_PUBLIC_API_URL ?? 'http://dms.localhost:8000';
const INTERNAL_BACKEND_ORIGIN =
  process.env.DMS_INTERNAL_API_URL ?? PUBLIC_BACKEND_ORIGIN;
const FRAPPE_SITE_NAME =
  process.env.DMS_FRAPPE_SITE ?? 'dms.localhost';

const COMPANY_ROUTE_MAP: Record<string, string[]> = {
  Honda: ['/honda'],
  NEXA: ['/nexa'],
  Jaguar: ['/jaguar'],
  Group: ['/admin', '/honda', '/nexa', '/jaguar'],
};

const DEFAULT_ROUTE_MAP: Record<string, string> = {
  Honda: '/honda',
  NEXA: '/nexa',
  Jaguar: '/jaguar',
  Group: '/admin',
};

type SessionUser = {
  company?: string;
};

function loginRedirect(request: NextRequest): NextResponse {
  const loginUrl = new URL('/login', request.url);
  loginUrl.searchParams.set('redirect', request.nextUrl.pathname);
  const response = NextResponse.redirect(loginUrl);
  response.cookies.delete('sid');
  return response;
}

async function loadSessionUser(
  sessionId: string,
): Promise<SessionUser | null> {
  try {
    const response = await fetch(
      `${INTERNAL_BACKEND_ORIGIN}/api/method/dms.api.auth.me`,
      {
        method: 'GET',
        headers: {
          Accept: 'application/json',
          Cookie: `sid=${sessionId}`,
          'X-Frappe-Site-Name': FRAPPE_SITE_NAME,
        },
        cache: 'no-store',
      },
    );

    if (!response.ok) return null;

    const raw = await response.json();
    const message =
      typeof raw?.message === 'object' && raw.message !== null
        ? raw.message
        : raw;
    const data =
      typeof message?.data === 'object' && message.data !== null
        ? message.data
        : message;
    const user =
      typeof data?.user === 'object' && data.user !== null
        ? data.user
        : null;

    return user;
  } catch {
    return null;
  }
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (PUBLIC_PATHS.some((publicPath) => pathname.startsWith(publicPath))) {
    return NextResponse.next();
  }

  const sessionId = request.cookies.get('sid')?.value;
  if (!sessionId || sessionId === 'Guest') {
    return loginRedirect(request);
  }

  const user = await loadSessionUser(sessionId);
  const company = String(user?.company ?? '');
  if (!company) {
    return loginRedirect(request);
  }

  const isDashboardRoute =
    pathname.startsWith('/honda')
    || pathname.startsWith('/nexa')
    || pathname.startsWith('/jaguar')
    || pathname.startsWith('/admin');

  if (isDashboardRoute) {
    const allowedRoutes = COMPANY_ROUTE_MAP[company] ?? [];
    const allowed = allowedRoutes.some((route) =>
      pathname.startsWith(route),
    );
    if (!allowed) {
      return NextResponse.redirect(
        new URL(DEFAULT_ROUTE_MAP[company] ?? '/login', request.url),
      );
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico|grid.svg).*)'],
};
