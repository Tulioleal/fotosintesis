import "next-auth";
import "next-auth/jwt";
import type { DefaultSession } from "next-auth";

declare module "next-auth" {
  interface Session {
    backendSessionToken: string;
    user: {
      id: string;
      email_verified: boolean;
    } & DefaultSession["user"];
  }

  interface User {
    sessionToken?: string;
    sessionExpiresAt?: string;
    email_verified?: boolean;
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    sessionToken?: string;
    sessionExpiresAt?: string;
    email_verified?: boolean;
  }
}
