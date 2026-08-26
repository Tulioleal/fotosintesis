import { describe, expect, it } from "vitest";
import {
  findAuthCoreImports,
  verifyInstalledGraph,
  verifyManifest,
} from "./check-auth-dependencies.mjs";

const PIN = "5.0.0-beta.32";
const AUTH_CORE = "@auth/" + "core";
const AUTH_CORE_PART = "@auth/";

const validManifest = { dependencies: { "next-auth": PIN } };

const validGraph = [
  {
    name: "frontend",
    version: "0.1.0",
    dependencies: {
      "next-auth": { version: PIN, dependencies: { [AUTH_CORE]: { version: "0.41.3" } } },
    },
  },
];

describe("verifyManifest", () => {
  it("accepts an exact beta 32 pin with no direct @auth/core", () => {
    expect(verifyManifest(validManifest)).toEqual([]);
  });

  it("rejects a vulnerable beta 31 pin", () => {
    const failures = verifyManifest({ dependencies: { "next-auth": "5.0.0-beta.31" } });
    expect(failures).not.toEqual([]);
    expect(failures.join("\n")).toContain(PIN);
  });

  it("rejects an open version range", () => {
    expect(verifyManifest({ dependencies: { "next-auth": "^5.0.0-beta.25" } })).not.toEqual([]);
  });

  it("rejects a direct @auth/core declaration in dependencies", () => {
    const failures = verifyManifest({ dependencies: { "next-auth": PIN, [AUTH_CORE]: "^0.37.4" } });
    expect(failures).not.toEqual([]);
    expect(failures.join("\n")).toContain("dependencies");
  });

  it("rejects a direct @auth/core declaration in devDependencies", () => {
    const failures = verifyManifest({
      dependencies: { "next-auth": PIN },
      devDependencies: { [AUTH_CORE]: "^0.37.4" },
    });
    expect(failures).not.toEqual([]);
    expect(failures.join("\n")).toContain("devDependencies");
  });

  it("rejects a direct @auth/core declaration in optionalDependencies", () => {
    const failures = verifyManifest({
      dependencies: { "next-auth": PIN },
      optionalDependencies: { [AUTH_CORE]: "^0.37.4" },
    });
    expect(failures).not.toEqual([]);
    expect(failures.join("\n")).toContain("optionalDependencies");
  });

  it("rejects a direct @auth/core declaration in peerDependencies", () => {
    const failures = verifyManifest({
      dependencies: { "next-auth": PIN },
      peerDependencies: { [AUTH_CORE]: "^0.37.4" },
    });
    expect(failures).not.toEqual([]);
    expect(failures.join("\n")).toContain("peerDependencies");
  });
});

describe("verifyInstalledGraph", () => {
  it("accepts the intended aligned production graph", () => {
    expect(verifyInstalledGraph(validGraph)).toEqual([]);
  });

  it("rejects an installed vulnerable beta 31", () => {
    const graph = [
      {
        dependencies: {
          "next-auth": {
            version: "5.0.0-beta.31",
            dependencies: { [AUTH_CORE]: { version: "0.41.2" } },
          },
        },
      },
    ];
    const failures = verifyInstalledGraph(graph);
    expect(failures).not.toEqual([]);
    expect(failures.join("\n")).toContain(PIN);
  });

  it("rejects @auth/core reachable only beneath an unrelated package", () => {
    const graph = [
      {
        dependencies: {
          "next-auth": { version: PIN },
          "unrelated-package": { version: "1.0.0", dependencies: { [AUTH_CORE]: { version: "0.41.3" } } },
        },
      },
    ];
    const failures = verifyInstalledGraph(graph);
    expect(failures).not.toEqual([]);
    expect(failures.join("\n")).toContain("outside the next-auth subtree");
  });

  it("rejects a vulnerable @auth/core beneath next-auth", () => {
    const graph = [
      {
        dependencies: {
          "next-auth": { version: PIN, dependencies: { [AUTH_CORE]: { version: "0.37.4" } } },
        },
      },
    ];
    const failures = verifyInstalledGraph(graph);
    expect(failures).not.toEqual([]);
    expect(failures.join("\n")).toContain("0.41.3");
  });

  it("rejects multiple core versions beneath separate next-auth nodes", () => {
    const graph = [
      {
        dependencies: {
          "next-auth": { version: PIN, dependencies: { [AUTH_CORE]: { version: "0.41.3" } } },
          "wrapper": {
            version: "1.0.0",
            dependencies: {
              "next-auth": { version: PIN, dependencies: { [AUTH_CORE]: { version: "0.37.4" } } },
            },
          },
        },
      },
    ];
    const failures = verifyInstalledGraph(graph);
    expect(failures).not.toEqual([]);
    expect(failures.join("\n")).toContain("exactly one");
  });

  it("rejects additional @auth/core versions elsewhere in the graph", () => {
    const graph = [
      {
        dependencies: {
          "next-auth": { version: PIN, dependencies: { [AUTH_CORE]: { version: "0.41.3" } } },
          "some-other-pkg": { version: "1.0.0", dependencies: { [AUTH_CORE]: { version: "0.37.4" } } },
        },
      },
    ];
    const failures = verifyInstalledGraph(graph);
    expect(failures).not.toEqual([]);
    expect(failures.join("\n")).toContain("outside the next-auth subtree");
  });

  it("rejects a vulnerable Auth.js graph in a later project", () => {
    const graph = [
      { name: "frontend", dependencies: { "next-auth": { version: PIN, dependencies: { [AUTH_CORE]: { version: "0.41.3" } } } } },
      { name: "other-workspace", dependencies: { "next-auth": { version: "5.0.0-beta.31", dependencies: { [AUTH_CORE]: { version: "0.41.2" } } } } },
    ];
    const failures = verifyInstalledGraph(graph);
    expect(failures).not.toEqual([]);
    expect(failures.join("\n")).toContain(PIN);
  });

  it("rejects a missing transitive @auth/core", () => {
    const failures = verifyInstalledGraph([{ dependencies: { "next-auth": { version: PIN } } }]);
    expect(failures).not.toEqual([]);
    expect(failures.join("\n")).toContain("exactly one");
  });
});

describe("findAuthCoreImports", () => {
  const safeFile = { path: "src/lib/server/backend-session.ts", content: 'import { getToken } from "next-auth/jwt";' };

  it("accepts source with no @auth/core imports", () => {
    expect(findAuthCoreImports([safeFile])).toEqual([]);
  });

  it("rejects a static named import from @auth/core/jwt", () => {
    const violations = findAuthCoreImports([
      { path: "src/lib/server/backend-session.ts", content: `import { getToken } from "${AUTH_CORE}/jwt";` },
    ]);
    expect(violations).not.toEqual([]);
    expect(violations[0]).toContain("src/lib/server/backend-session.ts:1");
  });

  it("rejects a side-effect import from @auth/core", () => {
    const content = `import "${AUTH_CORE}";`;
    expect(findAuthCoreImports([{ path: "src/x.ts", content }])).not.toEqual([]);
  });

  it("rejects a re-export from @auth/core", () => {
    expect(findAuthCoreImports([{ path: "src/x.ts", content: `export * from "${AUTH_CORE}";` }])).not.toEqual([]);
  });

  it("rejects a dynamic import of @auth/core", () => {
    const content = `await import("${AUTH_CORE}/jwt");`;
    expect(findAuthCoreImports([{ path: "src/x.ts", content }])).not.toEqual([]);
  });

  it("rejects a CommonJS require of @auth/core", () => {
    const content = `const jwt = require("${AUTH_CORE}/jwt");`;
    expect(findAuthCoreImports([{ path: "src/x.ts", content }])).not.toEqual([]);
  });

  it("rejects a multi-line static import from @auth/core", () => {
    const content = `import {\n  getToken,\n} from "${AUTH_CORE}/jwt";`;
    expect(findAuthCoreImports([{ path: "src/x.ts", content }])).not.toEqual([]);
  });

  it("rejects a computed dynamic import", () => {
    const content = `import("${AUTH_CORE_PART}" + "core");`;
    expect(findAuthCoreImports([{ path: "src/x.ts", content }])).not.toEqual([]);
  });

  it("rejects a computed CommonJS require", () => {
    const content = `require("${AUTH_CORE_PART}" + "core/jwt");`;
    expect(findAuthCoreImports([{ path: "src/x.ts", content }])).not.toEqual([]);
  });

  it("rejects a comment-separated dynamic import", () => {
    const content = `import/*gap*/("${AUTH_CORE}");`;
    expect(findAuthCoreImports([{ path: "src/x.ts", content }])).not.toEqual([]);
  });

  it("rejects a comment-separated CommonJS require", () => {
    const content = `require/*gap*/("${AUTH_CORE}/jwt");`;
    expect(findAuthCoreImports([{ path: "src/x.ts", content }])).not.toEqual([]);
  });

  it("rejects a template-literal dynamic import", () => {
    const content = "import(`" + "@auth/" + `\${"core"}` + `/jwt` + "`);";
    expect(findAuthCoreImports([{ path: "src/x.ts", content }])).not.toEqual([]);
  });

  it("rejects a TypeScript import-equals require", () => {
    const content = `import x = require("${AUTH_CORE}");`;
    expect(findAuthCoreImports([{ path: "src/x.ts", content }])).not.toEqual([]);
  });

  it("rejects a TypeScript import type", () => {
    const content = `let T: import("${AUTH_CORE}").User;`;
    expect(findAuthCoreImports([{ path: "src/x.ts", content }])).not.toEqual([]);
  });

  it("reports the exact line of an import", () => {
    const content = `// header line\n\nimport { getToken } from "${AUTH_CORE}/jwt";`;
    const violations = findAuthCoreImports([{ path: "src/x.ts", content }]);
    expect(violations).toEqual([expect.stringContaining("src/x.ts:3")]);
  });

  it("fails when a scanned source file cannot be parsed and reports a real line", () => {
    const content = `const leading = 1;\nimport { getToken from "${AUTH_CORE}/jwt";`;
    const violations = findAuthCoreImports([{ path: "src/x.ts", content }]);
    expect(violations).not.toEqual([]);
    expect(violations[0]).toContain("src/x.ts:");
    expect(violations[0]).toMatch(/src\/x\.ts:[1-9][0-9]*:/);
    expect(violations[0]).not.toContain("src/x.ts:0:");
    expect(violations[0]).toContain("could not parse source");
  });

  it("does not flag a safe string that only mentions @auth/core", () => {
    const content = `const message = "plain @auth/" + "core mention";`;
    expect(findAuthCoreImports([{ path: "src/x.ts", content }])).toEqual([]);
  });

  it("does not flag a comment that only mentions @auth/core", () => {
    const content = `// @auth/" + "core was replaced by next-auth/jwt\nimport { getToken } from "next-auth/jwt";`;
    expect(findAuthCoreImports([{ path: "src/x.ts", content }])).toEqual([]);
  });

  it("allows the @auth/coreish control", () => {
    const content = `import { x } from "@auth/coreish";`;
    expect(findAuthCoreImports([{ path: "src/x.ts", content }])).toEqual([]);
  });

  it("allows the @auth/core-client control", () => {
    const content = `import { x } from "@auth/core-client";`;
    expect(findAuthCoreImports([{ path: "src/x.ts", content }])).toEqual([]);
  });

  it("rejects a static const dynamic import", () => {
    const content = `const target = "${AUTH_CORE}";\nimport(target);`;
    expect(findAuthCoreImports([{ path: "src/x.ts", content }])).not.toEqual([]);
  });

  it("rejects a static const CommonJS require", () => {
    const content = `const jwtPackage = "${AUTH_CORE_PART}" + "core/jwt";\nrequire(jwtPackage);`;
    expect(findAuthCoreImports([{ path: "src/x.ts", content }])).not.toEqual([]);
  });

  it("rejects an immutable binding nested inside a lexical scope", () => {
    const content = `const target = "next-auth/jwt";\n{\n  const target = "${AUTH_CORE}";\n  import(target);\n}`;
    expect(findAuthCoreImports([{ path: "src/x.ts", content }])).not.toEqual([]);
  });

  it("resolves the innermost lexical binding for dynamic imports", () => {
    const content = `const target = "${AUTH_CORE}";\n{\n  const target = "next-auth/jwt";\n  import(target);\n}`;
    expect(findAuthCoreImports([{ path: "src/x.ts", content }])).toEqual([]);
  });

  it("does not flag a reassigned let binding", () => {
    const content = `let target = "${AUTH_CORE}";\ntarget = "next-auth/jwt";\nimport(target);`;
    expect(findAuthCoreImports([{ path: "src/x.ts", content }])).toEqual([]);
  });

  it("does not flag a function-produced specifier binding", () => {
    const content = `const target = makeSpec();\nimport(target);`;
    expect(findAuthCoreImports([{ path: "src/x.ts", content }])).toEqual([]);
  });

  it("does not flag cyclic bindings", () => {
    const content = `const a = b;\nconst b = a;\nimport(a);`;
    expect(findAuthCoreImports([{ path: "src/x.ts", content }])).toEqual([]);
  });

  it("does not treat a shadowed local require as a CommonJS load", () => {
    const content = `const require = (id) => id;\nrequire("${AUTH_CORE}");`;
    expect(findAuthCoreImports([{ path: "src/x.ts", content }])).toEqual([]);
  });

  it("rejects a real CommonJS require even with other local functions present", () => {
    const content = `function local(id) { return id; }\nconst jwtPackage = "${AUTH_CORE_PART}" + "core/jwt";\nrequire(jwtPackage);`;
    expect(findAuthCoreImports([{ path: "src/x.ts", content }])).not.toEqual([]);
  });
});
