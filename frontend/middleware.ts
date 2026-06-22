import { NextResponse, type NextRequest } from 'next/server';

const PUBLIC_PATHS = ['/login', '/forgot-password'];

const COMPANY_ROUTE_MAP: Record<string, string[]> = {
  Honda: ['/honda'],
  NEXA: ['/nexa'],
  Jaguar: ['/jaguar'],
  Group: ['/admin', '/honda', '/nexa', '/jaguar'],
};

function parseJWTPayload(token: string): Record<string, unknown> | null {
  try {
    const [, payload] = token.split('.');
    return JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/')));
  } catch {
    return null;
  }
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (PUBLIC_PATHS.some((p) => pathname.startsWith(p))) {
    return NextResponse.next();
  }

  const token = request.cookies.get('dms_access_token')?.value;

  if (!token) {
    const loginUrl = new URL('/login', request.url);
    loginUrl.searchParams.set('redirect', pathname);
    return NextResponse.redirect(loginUrl);
  }

  const payload = parseJWTPayload(token);
  if (!payload || (payload.exp as number) * 1000 < Date.now()) {
    const loginUrl = new URL('/login', request.url);
    return NextResponse.redirect(loginUrl);
  }

  const company = payload.company as string;
  const allowedRoutes = COMPANY_ROUTE_MAP[company] ?? [];
  const isDashboardRoute =
    pathname.startsWith('/honda') ||
    pathname.startsWith('/nexa') ||
    pathname.startsWith('/jaguar') ||
    pathname.startsWith('/admin');

  if (isDashboardRoute && allowedRoutes.length > 0) {
    const hasAccess = allowedRoutes.some((r) => pathname.startsWith(r));
    if (!hasAccess) {
      const dashboardMap: Record<string, string> = {
        Honda: '/honda',
        NEXA: '/nexa',
        Jaguar: '/jaguar',
        Group: '/admin',
      };
      return NextResponse.redirect(new URL(dashboardMap[company] ?? '/login', request.url));
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico|grid.svg).*)'],
};
