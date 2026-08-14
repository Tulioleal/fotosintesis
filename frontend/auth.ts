import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import { z } from "zod";
import { API_BASE_URL } from "@/lib/api/config";
import { authTokenSchema } from "@/lib/server/auth-token";
import type { JWT } from "next-auth/jwt";
import type { Session } from "next-auth";
import type { components } from "@/lib/generated/openapi";

type CredentialsVerifyResponse = components["schemas"]["CredentialsVerifyResponse"];

const credentialsSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
});

const credentialsVerifyResponseSchema: z.ZodType<CredentialsVerifyResponse> = z.object({
  user: z.object({
    id: z.string().min(1),
    name: z.string().min(1),
    email: z.string().email(),
    email_verified: z.boolean(),
  }),
  session_token: z.string().min(1),
  session_expires_at: z.string().refine((value) => !Number.isNaN(Date.parse(value)), {
    message: "session_expires_at must be a valid date",
  }),
});

const callbackUserSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  email: z.string().email(),
  backendCredential: z.string().min(1),
  sessionExpiresAt: z.string().refine((value) => !Number.isNaN(Date.parse(value)), {
    message: "sessionExpiresAt must be a valid date",
  }),
  email_verified: z.boolean(),
});

type CallbackUser = z.infer<typeof callbackUserSchema>;

export const AUTHENTICATION_ERROR = "Authentication error";

export async function verifyCredentials(credentials: unknown): Promise<CallbackUser | null> {
  const parsed = credentialsSchema.safeParse(credentials);
  if (!parsed.success) return null;

  const response = await fetch(`${API_BASE_URL}/auth/credentials/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(parsed.data),
  });
  if (!response.ok) return null;

  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return null;
  }

  const validated = credentialsVerifyResponseSchema.safeParse(payload);
  if (!validated.success) return null;

  return {
    id: validated.data.user.id,
    name: validated.data.user.name,
    email: validated.data.user.email,
    backendCredential: validated.data.session_token,
    sessionExpiresAt: validated.data.session_expires_at,
    email_verified: validated.data.user.email_verified,
  };
}

export function createJwtToken(token: JWT, user: unknown): JWT {
  const parsed = callbackUserSchema.safeParse(user);
  if (!parsed.success) {
    throw new Error(AUTHENTICATION_ERROR);
  }
  const validated = parsed.data;
  return {
    ...token,
    sub: validated.id,
    backendCredential: validated.backendCredential,
    sessionExpiresAt: validated.sessionExpiresAt,
    email_verified: validated.email_verified,
  };
}

export function createBrowserSession(session: Session, token: JWT): Session {
  if (!session.user) {
    throw new Error(AUTHENTICATION_ERROR);
  }
  const parsed = authTokenSchema.safeParse(token);
  if (!parsed.success) {
    throw new Error(AUTHENTICATION_ERROR);
  }
  return {
    expires: session.expires,
    user: {
      id: parsed.data.sub,
      name: session.user.name,
      email: session.user.email,
      image: session.user.image,
      email_verified: parsed.data.email_verified,
    },
  };
}

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
        return verifyCredentials(credentials);
      },
    }),
  ],
  callbacks: {
    jwt({ token, user }) {
      if (user) {
        return createJwtToken(token, user);
      }
      return token;
    },
    session({ session, token }) {
      return createBrowserSession(session, token);
    },
  },
});
