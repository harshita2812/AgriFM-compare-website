import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const localPython = process.platform === "win32"
  ? join(root, ".venv", "Scripts", "python.exe")
  : join(root, ".venv", "bin", "python");
const python = process.env.AGRIFM_PYTHON || process.env.PYTHON || (existsSync(localPython) ? localPython : "python");
const result = spawnSync(python, ["-m", "unittest", "discover", "-s", "tests", "-v"], {
  cwd: root,
  stdio: "inherit",
});

if (result.error) {
  console.error(`Unable to launch Python test runner "${python}": ${result.error.message}`);
  process.exit(1);
}
process.exit(result.status ?? 1);
