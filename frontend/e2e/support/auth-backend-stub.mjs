import { createServer } from "node:http";
import { randomUUID } from "node:crypto";

const HOST = "127.0.0.1";
const PORT = Number(process.env.AUTH_STUB_PORT ?? 8099);
const SESSION_TTL_MS = 30 * 60 * 1000;
const SEED_EMAIL = "e2e-auth@example.com";
const SEED_PASSWORD = "password123";
const SEED_NAME = "E2E User";

const state = {
  users: new Map(),
  sessions: new Map(),
  logoutEvents: [],
  nextId: 1,
};

function publicUser(user) {
  return {
    id: user.id,
    name: user.name,
    email: user.email,
    email_verified: user.email_verified,
  };
}

function seed() {
  const user = {
    id: `00000000-0000-4000-8000-${String(state.nextId++).padStart(12, "0")}`,
    name: SEED_NAME,
    email: SEED_EMAIL,
    email_verified: true,
    password: SEED_PASSWORD,
  };
  state.users.set(SEED_EMAIL, user);
}

function reset() {
  state.users.clear();
  state.sessions.clear();
  state.logoutEvents.length = 0;
  state.nextId = 1;
  seed();
}

function createSession(userId) {
  const token = randomUUID();
  const expiresAt = new Date(Date.now() + SESSION_TTL_MS).toISOString();
  state.sessions.set(token, { userId, expiresAt, active: true });
  return { token, expiresAt };
}

function tokenFromRequest(req) {
  const authorization = req.headers.authorization ?? "";
  const bearerMatch = /^Bearer\s+(.+)$/.exec(authorization);
  if (bearerMatch) return { token: bearerMatch[1], via: "bearer" };
  const cookieMatch = /(?:^|;\s*)fotosintesis_session=([^;]+)/.exec(req.headers.cookie ?? "");
  if (cookieMatch) return { token: cookieMatch[1], via: "cookie" };
  return null;
}

function activeSession(req) {
  const found = tokenFromRequest(req);
  if (!found) return null;
  const session = state.sessions.get(found.token);
  if (!session || !session.active) return null;
  if (new Date(session.expiresAt).getTime() <= Date.now()) return null;
  return { session, token: found.token, via: found.via };
}

function setCorsHeaders(req, res) {
  const origin = req.headers.origin;
  if (origin) {
    res.setHeader("Access-Control-Allow-Origin", origin);
    res.setHeader("Access-Control-Allow-Credentials", "true");
    res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization, Accept");
    res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS, DELETE");
  }
}

function sendJson(res, status, payload) {
  const body = JSON.stringify(payload);
  res.writeHead(status, { "Content-Type": "application/json" });
  res.end(body);
}

async function readBody(req) {
  const chunks = [];
  for await (const chunk of req) {
    chunks.push(chunk);
  }
  const raw = Buffer.concat(chunks).toString("utf8");
  if (!raw) return {};
  try {
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

async function handle(req, res, url) {
  const { pathname } = url;

  if (req.method === "GET" && pathname === "/health") {
    return sendJson(res, 200, { status: "ok" });
  }

  if (req.method === "POST" && pathname === "/__test__/reset") {
    reset();
    return sendJson(res, 200, { status: "ok" });
  }

  if (req.method === "GET" && pathname === "/__test__/state") {
    return sendJson(res, 200, {
      seededEmail: SEED_EMAIL,
      users: [...state.users.values()].map((user) => publicUser(user)),
      activeSessions: [...state.sessions.entries()]
        .filter(([, session]) => session.active)
        .map(([token, session]) => ({ token, userId: session.userId, expiresAt: session.expiresAt })),
      logoutEvents: state.logoutEvents,
    });
  }

  if (req.method === "POST" && pathname === "/auth/register") {
    const body = await readBody(req);
    const email = typeof body.email === "string" ? body.email : "";
    const password = typeof body.password === "string" ? body.password : "";
    const name = typeof body.name === "string" ? body.name : "";
    if (!email || !password || !name) {
      return sendJson(res, 422, { detail: "name, email, and password are required" });
    }
    if (state.users.has(email)) {
      return sendJson(res, 409, { detail: "An account with that email already exists" });
    }
    const user = {
      id: `00000000-0000-4000-8000-${String(state.nextId++).padStart(12, "0")}`,
      name,
      email,
      email_verified: true,
      password,
    };
    state.users.set(email, user);
    return sendJson(res, 201, { user: publicUser(user) });
  }

  if (req.method === "POST" && pathname === "/auth/credentials/verify") {
    const body = await readBody(req);
    const user = state.users.get(String(body.email ?? ""));
    if (!user || user.password !== String(body.password ?? "")) {
      return sendJson(res, 401, { detail: "Invalid credentials" });
    }
    const { token, expiresAt } = createSession(user.id);
    return sendJson(res, 200, {
      user: publicUser(user),
      session_token: token,
      session_expires_at: expiresAt,
    });
  }

  if (req.method === "GET" && pathname === "/auth/session") {
    if (!activeSession(req)) {
      return sendJson(res, 401, { detail: "Unauthorized" });
    }
    return sendJson(res, 200, { status: "ok" });
  }

  if (req.method === "POST" && pathname === "/auth/logout") {
    const found = tokenFromRequest(req);
    if (found && state.sessions.has(found.token)) {
      state.sessions.get(found.token).active = false;
      state.logoutEvents.push({ token: found.token, via: found.via, at: new Date().toISOString() });
    }
    return sendJson(res, 200, { status: "ok" });
  }

  if (req.method === "POST" && pathname === "/auth/recovery/request") {
    return sendJson(res, 200, {
      status: "ok",
      message: "Si el correo existe, te enviaremos instrucciones.",
    });
  }

  if (req.method === "GET" && pathname === "/home/summary") {
    const auth = activeSession(req);
    if (!auth) {
      return sendJson(res, 401, { detail: "Unauthorized" });
    }
    const user = [...state.users.values()].find((candidate) => candidate.id === auth.session.userId);
    if (!user) {
      return sendJson(res, 401, { detail: "Unauthorized" });
    }
    return sendJson(res, 200, {
      access: [],
      empty_state: true,
      garden_count: 0,
      recent_garden_plants: [],
      user: publicUser(user),
    });
  }

  return sendJson(res, 404, { detail: "Not found" });
}

const server = createServer(async (req, res) => {
  setCorsHeaders(req, res);
  if (req.method === "OPTIONS") {
    res.writeHead(204);
    res.end();
    return;
  }
  try {
    await handle(req, res, new URL(req.url ?? "/", `http://${HOST}:${PORT}`));
  } catch {
    sendJson(res, 500, { detail: "stub error" });
  }
});

server.listen(PORT, HOST, () => {
  reset();
  process.stdout.write(`auth backend stub listening on http://${HOST}:${PORT}\n`);
});
