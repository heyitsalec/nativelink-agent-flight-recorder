/** @deprecated Use truth-guard.mjs — kept for wave-13 proof gate naming parity. */
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const script = path.join(path.dirname(fileURLToPath(import.meta.url)), "truth-guard.mjs");
const result = spawnSync(process.execPath, [script], { stdio: "inherit", env: process.env });
process.exit(result.status ?? 1);
