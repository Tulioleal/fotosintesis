import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import { z } from "zod";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const credentialsSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
});

export const { handlers, signIn, signOut, auth } = NextAuth({
  pages: {
    signIn: "/login",
  },
  session: {
    strategy: "jwt",
    maxAge: 60 * 30,
    updateAge: 60 * 5,
  },
  providers: [
    Credentials({
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Contraseña", type: "password" },
      },
      async authorize(credentials) {
        const parsed = credentialsSchema.safeParse(credentials);
        if (!parsed.success) return null;

        const response = await fetch(`${API_BASE_URL}/auth/credentials/verify`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(parsed.data),
        });

        if (!response.ok) return null;
        const payload = (await response.json()) as {
          user: { id: string; name: string; email: string; email_verified: boolean };
          session_token: string;
          session_expires_at: string;
        };

        return {
          id: payload.user.id,
          name: payload.user.name,
          email: payload.user.email,
          sessionToken: payload.session_token,
          sessionExpiresAt: payload.session_expires_at,
          email_verified: payload.user.email_verified,
        };
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.sessionToken = (user as typeof user & { sessionToken?: string }).sessionToken;
        token.sessionExpiresAt = (user as typeof user & { sessionExpiresAt?: string }).sessionExpiresAt;
        token.email_verified = (user as typeof user & { email_verified?: boolean }).email_verified;
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        session.user.id = token.sub ?? "";
        session.user.email_verified = Boolean(token.email_verified);
      }
      session.backendSessionToken = String(token.sessionToken ?? "");
      return session;
    },
  },
});
