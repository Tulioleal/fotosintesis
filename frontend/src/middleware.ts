import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { validateBackendSession } from "@/lib/server/backend-session";

const privateRoutes = [
  "/home",
  "/identify",
  "/search",
  "/light-meter",
  "/reminders",
  "/garden",
  "/assistant",
];

export default async function middleware(request: NextRequest) {
  const isPrivateRoute = privateRoutes.some((route) => request.nextUrl.pathname.startsWith(route));
  if (isPrivateRoute && !(await validateBackendSession(request))) {
    const loginUrl = new URL("/login", request.nextUrl.origin);
    loginUrl.searchParams.set("callbackUrl", `${request.nextUrl.pathname}${request.nextUrl.search}`);
    return NextResponse.redirect(loginUrl);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/home/:path*", "/identify/:path*", "/search/:path*", "/light-meter/:path*", "/reminders/:path*", "/garden/:path*", "/assistant/:path*"],
};
