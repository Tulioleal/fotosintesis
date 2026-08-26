import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { spawnSync } from "node:child_process";

const frontendRoot = resolve(import.meta.dirname, "..");
const repositoryRoot = resolve(frontendRoot, "..");
const baselinePath = join(repositoryRoot, "backend", "openapi-baseline.json");
const generatedJsonPath = join(frontendRoot, "src", "lib", "generated", "openapi.json");
const generatedTypesPath = join(frontendRoot, "src", "lib", "generated", "openapi.d.ts");
const temporaryDirectory = await mkdtemp(join(tmpdir(), "fotosintesis-openapi-"));

async function assertSame(expectedPath, actualPath, label) {
  const [expected, actual] = await Promise.all([
    readFile(expectedPath),
    readFile(actualPath),
  ]);
  if (!expected.equals(actual)) {
    console.error(`${label} is stale. Run: pnpm --dir frontend openapi:generate`);
    process.exitCode = 1;
  }
}

try {
  const temporaryJsonPath = join(temporaryDirectory, "openapi.json");
  const temporaryTypesPath = join(temporaryDirectory, "openapi.d.ts");
  await writeFile(temporaryJsonPath, await readFile(baselinePath));

  const generation = spawnSync(
    "pnpm",
    [
      "exec",
      "openapi-typescript",
      temporaryJsonPath,
      "-o",
      temporaryTypesPath,
    ],
    { cwd: frontendRoot, encoding: "utf-8" },
  );
  if (generation.status !== 0) {
    process.stderr.write(generation.stderr || generation.stdout);
    process.exitCode = generation.status || 1;
  } else {
    await assertSame(baselinePath, generatedJsonPath, "Generated OpenAPI JSON");
    await assertSame(temporaryTypesPath, generatedTypesPath, "Generated OpenAPI types");
  }
} finally {
  await rm(temporaryDirectory, { recursive: true, force: true });
}
