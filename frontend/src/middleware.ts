import { NextResponse } from "next/server";
import { auth } from "../auth";

const privateRoutes = [
  "/home",
  "/identify",
  "/search",
  "/light-meter",
  "/reminders",
  "/garden",
  "/assistant",
];

export default auth((request) => {
  const isPrivateRoute = privateRoutes.some((route) => request.nextUrl.pathname.startsWith(route));
  if (isPrivateRoute && !request.auth) {
    const loginUrl = new URL("/login", request.nextUrl.origin);
    loginUrl.searchParams.set("callbackUrl", request.nextUrl.pathname);
    return NextResponse.redirect(loginUrl);
  }
  return NextResponse.next();
});

export const config = {
  matcher: ["/home/:path*", "/identify/:path*", "/search/:path*", "/light-meter/:path*", "/reminders/:path*", "/garden/:path*", "/assistant/:path*"],
};
