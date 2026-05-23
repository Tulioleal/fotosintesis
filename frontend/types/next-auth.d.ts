import "next-auth";
import "next-auth/jwt";
import type { DefaultSession } from "next-auth";

declare module "next-auth" {
  interface Session {
    user: {
      id: string;
      email_verified: boolean;
    } & DefaultSession["user"];
  }

  interface User {
    sessionExpiresAt?: string;
    email_verified?: boolean;
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    sessionExpiresAt?: string;
    email_verified?: boolean;
  }
}
