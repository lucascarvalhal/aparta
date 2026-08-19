#!/usr/bin/env node
// Thin launcher for the aparta Python CLI: runs the matching PyPI version
// through uvx (preferred) or pipx, so `npx aparta` works in Node-first setups.

const { spawnSync } = require("node:child_process");
const { version } = require("./package.json");

const args = process.argv.slice(2);

function tryRun(cmd, cmdArgs) {
  const result = spawnSync(cmd, cmdArgs, { stdio: "inherit" });
  if (result.error && result.error.code === "ENOENT") return null;
  return result.status ?? 1;
}

let status = tryRun("uvx", [`aparta==${version}`, ...args]);
if (status === null) status = tryRun("pipx", ["run", `aparta==${version}`, ...args]);

if (status === null) {
  console.error(
    [
      "aparta is a Python CLI and needs uv or pipx to run.",
      "",
      "Install uv (recommended):",
      "  curl -LsSf https://astral.sh/uv/install.sh | sh",
      "",
      "Or install aparta directly:",
      "  pip install aparta",
      "",
      "Then run `aparta` (or `npx aparta` again).",
    ].join("\n")
  );
  process.exit(1);
}

process.exit(status);
