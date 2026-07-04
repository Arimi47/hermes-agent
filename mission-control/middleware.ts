import { NextRequest, NextResponse } from 'next/server';

// Basic-Auth-Gate für das gesamte Dashboard. Ohne dieses Middleware war
// Mission Control öffentlich: kompletter Graph lesbar und via
// POST /api/tasks/status sogar in den Vault schreibbar.
//
// Credentials sind bewusst dieselben wie fürs Agent-Admin-API
// (HERMES_ADMIN_USER / HERMES_ADMIN_PASS, bereits am Railway-Service
// gesetzt): kein zweites Secret, und eine Passwort-Rotation deckt
// Agent + Dashboard gemeinsam ab.

function timingSafeEqual(a: string, b: string): boolean {
  // Edge runtime has no crypto.timingSafeEqual; compare without
  // early-exit so response time doesn't leak the match prefix length.
  const len = Math.max(a.length, b.length);
  let diff = a.length ^ b.length;
  for (let i = 0; i < len; i++) {
    diff |= (a.charCodeAt(i) || 0) ^ (b.charCodeAt(i) || 0);
  }
  return diff === 0;
}

export function middleware(req: NextRequest) {
  const user = process.env.HERMES_ADMIN_USER;
  const pass = process.env.HERMES_ADMIN_PASS;
  if (!user || !pass) {
    // Fail closed: lieber ein totes Dashboard als ein offenes.
    return new NextResponse('auth not configured (HERMES_ADMIN_USER/PASS missing)', {
      status: 503,
    });
  }

  const expected = 'Basic ' + btoa(`${user}:${pass}`);
  const given = req.headers.get('authorization') ?? '';
  if (timingSafeEqual(given, expected)) {
    return NextResponse.next();
  }

  return new NextResponse('authentication required', {
    status: 401,
    headers: { 'WWW-Authenticate': 'Basic realm="mission-control"' },
  });
}

export const config = {
  // Alles außer Next-internen Assets. Explizit KEINE Ausnahme für /api.
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
};
