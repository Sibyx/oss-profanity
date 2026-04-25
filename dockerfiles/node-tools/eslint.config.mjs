// IP-013: baseline ESLint flat-config used by every worker host.
// Lives next to its package.json so ESM resolves @eslint/js and
// typescript-eslint from /opt/node-tools/node_modules/. Committed to
// the repo for auditability; the Dockerfile COPYs the whole
// dockerfiles/node-tools/ directory to /opt/node-tools/.
//
// Pin versions live in dockerfiles/node-tools/package.json:
//   eslint@10.2.1, @eslint/js@10.0.1, typescript-eslint@8.59.0
// Bumping any of those changes what `recommended` means — treat this
// file and the package.json pins as one atomic unit.

import js from "@eslint/js";
import tseslint from "typescript-eslint";

export default [
  {
    files: ["**/*.{js,mjs,cjs,jsx,ts,tsx}"],
    ...js.configs.recommended,
  },
  ...tseslint.configs.recommended,
];
