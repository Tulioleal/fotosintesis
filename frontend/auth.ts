import NextAuth, { CredentialsSignin } from "next-auth";
import Credentials from "next-auth/providers/credentials";
import { z } from "zod";
import { API_BASE_URL } from "@/lib/api/config";
import { authTokenSchema } from "@/lib/server/auth-token";
import {
  AUTH_DEFAULT_UNAVAILABLE_SECONDS,
  encodeRetryCode,
  encodeUnavailableCode,
  parseRetryAfter,
} from "@/lib/server/auth-rate-limit";
import { buildInternalAuthHeaders, deriveSourceIdentity } from "@/lib/server/source-identity";
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

export class CredentialsRateLimited extends CredentialsSignin {
  code = "credentials_rate_limited";
  readonly retryAfterSeconds: number;

  constructor(retryAfterSeconds: number) {
    super();
    this.retryAfterSeconds = retryAfterSeconds;
    this.code = encodeRetryCode(retryAfterSeconds);
  }
}

export class CredentialsUnavailable extends CredentialsSignin {
  code = "temporarily_unavailable";
  readonly retryAfterSeconds: number;

  constructor(retryAfterSeconds: number) {
    super();
    this.retryAfterSeconds = retryAfterSeconds;
    this.code = encodeUnavailableCode(retryAfterSeconds);
  }
}

export type VerifyCredentialsResult =
  | { status: "ok"; user: CallbackUser }
  | { status: "invalid" }
  | { status: "rate_limited"; retryAfterSeconds: number }
  | { status: "unavailable"; retryAfterSeconds?: number };

export async function verifyCredentials(
  credentials: unknown,
  request: Request | null = null,
): Promise<VerifyCredentialsResult> {
  const parsed = credentialsSchema.safeParse(credentials);
  if (!parsed.success) return { status: "invalid" };

  const source = deriveSourceIdentity(request ?? new Request("http://local.invalid"));
  const headers = buildInternalAuthHeaders(source);

  const response = await fetch(`${API_BASE_URL}/auth/credentials/verify`, {
    method: "POST",
    headers,
    body: JSON.stringify(parsed.data),
  });
  if (response.status === 429) {
    const retryAfter = parseRetryAfter(response.headers.get("retry-after")) ?? 0;
    return { status: "rate_limited", retryAfterSeconds: retryAfter };
  }
  if (response.status === 503) {
    const retryAfter = parseRetryAfter(response.headers.get("retry-after")) ?? undefined;
    return { status: "unavailable", retryAfterSeconds: retryAfter };
  }
  if (!response.ok) return { status: "invalid" };

  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return { status: "invalid" };
  }

  const validated = credentialsVerifyResponseSchema.safeParse(payload);
  if (!validated.success) return { status: "invalid" };

  return {
    status: "ok",
    user: {
      id: validated.data.user.id,
      name: validated.data.user.name,
      email: validated.data.user.email,
      backendCredential: validated.data.session_token,
      sessionExpiresAt: validated.data.session_expires_at,
      email_verified: validated.data.user.email_verified,
    },
  };
}

export function mapVerifyCredentialsResult(
  result: VerifyCredentialsResult,
): CallbackUser | null {
  if (result.status === "ok") return result.user;
  if (result.status === "rate_limited") {
    throw new CredentialsRateLimited(result.retryAfterSeconds);
  }
  if (result.status === "unavailable") {
    throw new CredentialsUnavailable(result.retryAfterSeconds ?? AUTH_DEFAULT_UNAVAILABLE_SECONDS);
  }
  return null;
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
      async authorize(credentials, request) {
        return mapVerifyCredentialsResult(await verifyCredentials(credentials, request));
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
