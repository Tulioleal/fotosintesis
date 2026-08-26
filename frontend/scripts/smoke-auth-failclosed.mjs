import { spawn } from "node:child_process";
import { dirname, resolve } from "node:path";
import { env } from "node:process";
import { fileURLToPath } from "node:url";

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const PORT = process.env.AUTH_SMOKE_PORT ?? "3123";
const BASE_URL = `http://127.0.0.1:${PORT}`;
const PRIVATE_MARKER = "Cerrar sesión";
const READY_TIMEOUT_MS = 60000;
const REQUEST_TIMEOUT_MS = 10000;

function startServer() {
  const serverEnv = { ...env };
  delete serverEnv.AUTH_SECRET;
  delete serverEnv.NEXTAUTH_SECRET;
  serverEnv.AUTH_URL = BASE_URL;

  const child = spawn("pnpm", ["start", "-p", PORT], {
    cwd: frontendRoot,
    env: serverEnv,
    stdio: ["ignore", "pipe", "pipe"],
    detached: true,
  });
  let output = "";
  child.stdout.on("data", (chunk) => {
    output += chunk;
  });
  child.stderr.on("data", (chunk) => {
    output += chunk;
  });
  return { child, getOutput: () => output };
}

async function waitUntilReady(baseUrl) {
  const deadline = Date.now() + READY_TIMEOUT_MS;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${baseUrl}/login`, {
        redirect: "manual",
        signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      });
      if (response.status === 200) return;
    } catch {
      // server not ready yet
    }
    await new Promise((resolveWait) => setTimeout(resolveWait, 500));
  }
  throw new Error(`production frontend did not become ready on ${baseUrl}`);
}

let exitCode = 0;
let child = null;
try {
  const server = startServer();
  child = server.child;
  await waitUntilReady(BASE_URL);

  const response = await fetch(`${BASE_URL}/home`, {
    redirect: "manual",
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  });
  const location = response.headers.get("location") ?? "";
  const body = await response.text();

  const isRedirect = response.status === 307 || response.status === 308;
  if (!isRedirect) {
    console.error(
      `expected 307/308 redirect for a private route without AUTH_SECRET, got status ${response.status}`,
    );
    exitCode = 1;
  }

  let parsedLocation = null;
  try {
    parsedLocation = new URL(location, BASE_URL);
  } catch {
    console.error(`redirect location was not a valid URL: ${location}`);
    exitCode = 1;
  }
  if (parsedLocation && parsedLocation.pathname !== "/login") {
    console.error(`expected redirect to /login, got ${location}`);
    exitCode = 1;
  }
  if (body.includes(PRIVATE_MARKER)) {
    console.error(`private content leaked on the fail-closed redirect: found "${PRIVATE_MARKER}"`);
    exitCode = 1;
  }

  if (exitCode === 0) {
    console.log(`fail-closed smoke passed: /home without AUTH_SECRET redirected to ${location}`);
  } else {
    console.error(server.getOutput());
  }
} catch (error) {
  console.error(`fail-closed smoke failed: ${error instanceof Error ? error.message : String(error)}`);
  exitCode = 1;
} finally {
  if (child) {
    const groupPid = -child.pid;
    child.kill("SIGTERM");
    try {
      process.kill(groupPid, "SIGTERM");
    } catch {
      // process group already gone
    }
    await new Promise((resolveExit) => {
      const timer = setTimeout(() => {
        try {
          process.kill(groupPid, "SIGKILL");
        } catch {
          // process group already gone
        }
        resolveExit();
      }, 5000);
      child.once("exit", () => {
        clearTimeout(timer);
        resolveExit();
      });
    });
  }
}
process.exit(exitCode);
