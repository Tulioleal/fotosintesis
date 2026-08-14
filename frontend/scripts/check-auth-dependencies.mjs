import { readFile, readdir } from "node:fs/promises";
import { dirname, join, relative, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath, pathToFileURL } from "node:url";
import parser from "@typescript-eslint/parser";

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");

const NEXT_AUTH_PIN = "5.0.0-beta.32";
const AUTH_PACKAGE_NAMES = new Set(["next-auth", "@auth/core"]);
const AUTH_SOURCE_EXTENSIONS = new Set([".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"]);
const MANIFEST_DEPENDENCY_SECTIONS = [
  "dependencies",
  "devDependencies",
  "optionalDependencies",
  "peerDependencies",
];
const SKIPPED_SOURCE_DIRS = new Set([
  "node_modules",
  ".next",
  ".git",
  "test-results",
  "playwright-report",
  ".pnpm-store",
]);

function isAuthCoreSpecifier(specifier) {
  return specifier === "@auth/core" || specifier.startsWith("@auth/core/");
}

function resolveVariable(identifier, scopeManager) {
  if (!scopeManager?.scopes) return null;
  for (const scope of scopeManager.scopes) {
    for (const reference of scope.references) {
      if (reference.identifier === identifier) {
        return reference.resolved ?? null;
      }
    }
  }
  return null;
}

function resolveStaticString(node, context) {
  if (!node || typeof node !== "object") return null;
  switch (node.type) {
    case "Literal":
      return typeof node.value === "string" ? node.value : null;
    case "TemplateLiteral": {
      const parts = [];
      const quasis = node.quasis ?? [];
      const expressions = node.expressions ?? [];
      for (let index = 0; index < quasis.length; index += 1) {
        parts.push(quasis[index].value.cooked ?? quasis[index].value.raw ?? "");
        if (index < expressions.length) {
          const value = resolveStaticString(expressions[index], context);
          if (value === null) return null;
          parts.push(value);
        }
      }
      return parts.join("");
    }
    case "ParenthesizedExpression":
    case "TSAsExpression":
    case "TSNonNullExpression":
    case "TSSatisfiesExpression":
    case "TSTypeAssertion":
    case "TSLiteralType":
      return resolveStaticString(node.expression ?? node.literal, context);
    case "BinaryExpression": {
      if (node.operator !== "+") return null;
      const left = resolveStaticString(node.left, context);
      const right = resolveStaticString(node.right, context);
      if (left === null || right === null) return null;
      return left + right;
    }
    case "Identifier":
      return resolveIdentifierBinding(node, context);
    default:
      return null;
  }
}

function resolveIdentifierBinding(identifier, context) {
  const variable = resolveVariable(identifier, context.scopeManager);
  if (!variable) return null;
  const defs = variable.defs;
  if (defs.length !== 1) return null;
  const def = defs[0];
  const declarator = def?.node;
  if (!declarator || declarator.type !== "VariableDeclarator") return null;
  if (context.declaratorKinds.get(declarator) !== "const") return null;
  const reassigned = variable.references.some(
    (reference) => reference.isWrite() && reference.identifier !== def.name,
  );
  if (reassigned) return null;
  if (context.resolving.has(variable)) return null;
  const nextResolving = new Set(context.resolving);
  nextResolving.add(variable);
  return resolveStaticString(declarator.init, { ...context, resolving: nextResolving });
}

function extractSpecifier(node, context) {
  switch (node.type) {
    case "ImportDeclaration":
    case "ExportNamedDeclaration":
    case "ExportAllDeclaration":
      return resolveStaticString(node.source, context);
    case "ImportExpression":
      return resolveStaticString(node.source, context);
    case "CallExpression": {
      const callee = node.callee;
      if (callee?.type === "Identifier" && callee.name === "require" && node.arguments.length === 1) {
        if (resolveVariable(callee, context.scopeManager) !== null) {
          return null;
        }
        return resolveStaticString(node.arguments[0], context);
      }
      return null;
    }
    case "TSImportEqualsDeclaration": {
      const reference = node.moduleReference;
      if (reference?.type === "TSExternalModuleReference") {
        return resolveStaticString(reference.expression, context);
      }
      return null;
    }
    case "TSImportType":
      if (node.source) return resolveStaticString(node.source, context);
      return resolveStaticString(node.argument, context);
    default:
      return null;
  }
}

function walkAst(node, visitorKeys, visit) {
  if (!node || typeof node.type !== "string") return;
  visit(node);
  const keys = visitorKeys[node.type] ?? [];
  for (const key of keys) {
    const child = node[key];
    if (Array.isArray(child)) {
      for (const item of child) {
        if (item && typeof item === "object") walkAst(item, visitorKeys, visit);
      }
    } else if (child && typeof child === "object") {
      walkAst(child, visitorKeys, visit);
    }
  }
}

function sourceTypeFor(path) {
  return path.endsWith(".cjs") ? "commonjs" : "module";
}

function parseErrorLine(error, content) {
  if (typeof error?.lineNumber === "number") return error.lineNumber;
  if (typeof error?.loc?.line === "number") return error.loc.line;
  if (typeof error?.index === "number" && typeof content === "string") {
    return content.slice(0, error.index).split("\n").length;
  }
  return 1;
}

function scanSource(content, path) {
  const violations = [];
  let result;
  try {
    result = parser.parseForESLint(content, {
      ecmaVersion: 2024,
      sourceType: sourceTypeFor(path),
      filePath: path,
      loc: true,
      range: true,
    });
  } catch (error) {
    violations.push(`${path}:${parseErrorLine(error, content)}: could not parse source: ${error.message}`);
    return violations;
  }
  const visitorKeys = result.visitorKeys ?? {};
  const declaratorKinds = new Map();
  walkAst(result.ast, visitorKeys, (node) => {
    if (node.type === "VariableDeclaration") {
      for (const declarator of node.declarations) declaratorKinds.set(declarator, node.kind);
    }
  });
  const context = { scopeManager: result.scopeManager, declaratorKinds, resolving: new Set() };
  walkAst(result.ast, visitorKeys, (node) => {
    const specifier = extractSpecifier(node, context);
    if (specifier !== null && isAuthCoreSpecifier(specifier)) {
      const line = node.loc?.start?.line ?? 1;
      violations.push(`${path}:${line}: direct "@auth/core" import`);
    }
  });
  return violations;
}

export function verifyManifest(manifest) {
  const failures = [];
  const dependencies = manifest?.dependencies ?? {};
  const nextAuth = dependencies["next-auth"];
  if (nextAuth !== NEXT_AUTH_PIN) {
    failures.push(
      `frontend manifest must pin next-auth to exactly "${NEXT_AUTH_PIN}" (found ${JSON.stringify(nextAuth)})`,
    );
  }
  for (const section of MANIFEST_DEPENDENCY_SECTIONS) {
    const declared = manifest?.[section] ?? {};
    if (Object.prototype.hasOwnProperty.call(declared, "@auth/core")) {
      failures.push(
        `frontend manifest must not declare "@auth/core" directly in ${section} (found ${JSON.stringify(declared["@auth/core"])})`,
      );
    }
  }
  return failures;
}

export function collectAuthVersions(node, found = []) {
  const dependencies = node?.dependencies;
  if (dependencies && typeof dependencies === "object") {
    for (const [name, info] of Object.entries(dependencies)) {
      if (typeof info === "object" && info !== null && typeof info.version === "string") {
        if (AUTH_PACKAGE_NAMES.has(name)) {
          found.push({ name, version: info.version });
        }
      }
      if (typeof info === "object" && info !== null) {
        collectAuthVersions(info, found);
      }
    }
  }
  return found;
}

function collectEntries(node, entries = []) {
  const dependencies = node?.dependencies;
  if (dependencies && typeof dependencies === "object") {
    for (const [name, info] of Object.entries(dependencies)) {
      if (typeof info === "object" && info !== null && typeof info.version === "string") {
        entries.push({ name, version: info.version, node: info });
      }
      if (typeof info === "object" && info !== null) {
        collectEntries(info, entries);
      }
    }
  }
  return entries;
}

export function verifyInstalledGraph(graph) {
  const failures = [];
  const projects = Array.isArray(graph) ? graph : [graph];

  const allEntries = [];
  const nextAuthEntries = [];
  for (const project of projects) {
    const entries = collectEntries(project);
    allEntries.push(...entries);
    for (const entry of entries) {
      if (entry.name === "next-auth") nextAuthEntries.push(entry);
    }
  }

  if (nextAuthEntries.length === 0) {
    failures.push("installed production graph must contain next-auth (none found)");
  }
  for (const entry of nextAuthEntries) {
    if (entry.version !== NEXT_AUTH_PIN) {
      failures.push(
        `installed next-auth must be exactly "${NEXT_AUTH_PIN}" (found ${entry.version})`,
      );
    }
  }

  const beneathCoreEntries = [];
  for (const entry of nextAuthEntries) {
    beneathCoreEntries.push(...collectEntries(entry.node).filter((candidate) => candidate.name === "@auth/core"));
  }
  const beneathCoreVersions = new Set(beneathCoreEntries.map((entry) => entry.version));
  if (beneathCoreVersions.size !== 1) {
    failures.push(
      `exactly one transitive "@auth/core" version must be reachable beneath next-auth (found ${[...beneathCoreVersions].join(", ") || "none"})`,
    );
  } else {
    const beneathCoreVersion = [...beneathCoreVersions][0];
    if (beneathCoreVersion !== "0.41.3") {
      failures.push(
        `transitive "@auth/core" beneath next-auth must be 0.41.3 (found ${beneathCoreVersion})`,
      );
    }
  }

  const beneathCoreNodes = new Set(beneathCoreEntries.map((entry) => entry.node));
  const elsewhereCore = allEntries.filter(
    (entry) => entry.name === "@auth/core" && !beneathCoreNodes.has(entry.node),
  );
  for (const entry of elsewhereCore) {
    failures.push(
      `additional "@auth/core" version ${entry.version} is reachable outside the next-auth subtree`,
    );
  }

  return failures;
}

export function findAuthCoreImports(files) {
  const violations = [];
  for (const { path, content } of files) {
    violations.push(...scanSource(content, path));
  }
  return violations;
}

export async function collectSourceFiles(root, base = root, files = []) {
  let entries;
  try {
    entries = await readdir(root, { withFileTypes: true });
  } catch {
    return files;
  }
  for (const entry of entries) {
    if (SKIPPED_SOURCE_DIRS.has(entry.name)) continue;
    const fullPath = join(root, entry.name);
    if (entry.isDirectory()) {
      await collectSourceFiles(fullPath, base, files);
    } else if (AUTH_SOURCE_EXTENSIONS.has(entry.name.slice(entry.name.lastIndexOf(".")))) {
      files.push({ path: relative(base, fullPath), fullPath });
    }
  }
  return files;
}

function runCommand(command, args) {
  const result = spawnSync(command, args, {
    cwd: frontendRoot,
    encoding: "utf-8",
    env: process.env,
  });
  return { status: result.status, stdout: result.stdout, stderr: result.stderr };
}

export async function run() {
  const failures = [];

  const manifest = JSON.parse(await readFile(join(frontendRoot, "package.json"), "utf8"));
  failures.push(...verifyManifest(manifest));

  const list = runCommand("pnpm", [
    "--filter",
    "frontend",
    "list",
    "--prod",
    "--depth",
    "Infinity",
    "--json",
  ]);
  if (list.status !== 0) {
    failures.push(`pnpm list failed: ${(list.stderr || list.stdout).trim()}`);
  } else {
    failures.push(...verifyInstalledGraph(JSON.parse(list.stdout)));
  }

  const sourceFiles = await collectSourceFiles(frontendRoot, frontendRoot);
  const contents = [];
  for (const file of sourceFiles) {
    contents.push({ path: file.path, content: await readFile(file.fullPath, "utf8") });
  }
  failures.push(...findAuthCoreImports(contents));

  if (failures.length > 0) {
    for (const failure of failures) {
      process.stderr.write(`error: ${failure}\n`);
    }
    process.stderr.write(`Authentication dependency security gate FAILED\n`);
    process.exitCode = 1;
  } else {
    process.stdout.write(
      `Authentication dependency security gate passed: next-auth pinned to ${NEXT_AUTH_PIN}, no direct @auth/core, one reachable core version, no direct core imports.\n`,
    );
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  run();
}
