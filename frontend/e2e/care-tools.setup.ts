import type { FullConfig } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const SEED_SCRIPT = resolve(here, "seed_care_state.py");
const CREDS_FILE = resolve(here, ".care-tools-credentials.json");

interface SeedOutput {
  email: string;
  password: string;
}

function seedCredentials(): SeedOutput {
  const out = execFileSync("python3", [SEED_SCRIPT], { encoding: "utf8" });
  const emailMatch = out.match(/^EMAIL=(.+)$/m);
  const passwordMatch = out.match(/^PASSWORD=(.+)$/m);
  if (!emailMatch || !passwordMatch) {
    throw new Error(`seed script did not return EMAIL/PASSWORD: ${out}`);
  }
  return { email: emailMatch[1], password: passwordMatch[1] };
}

export default async function globalSetup(_config: FullConfig) {
  mkdirSync(dirname(CREDS_FILE), { recursive: true });
  const creds = seedCredentials();
  writeFileSync(CREDS_FILE, JSON.stringify(creds));
}

export function readCareToolsCredentials(): SeedOutput {
  return JSON.parse(readFileSync(CREDS_FILE, "utf8")) as SeedOutput;
}
