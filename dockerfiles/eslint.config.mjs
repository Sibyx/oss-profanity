// IP-009: baseline ESLint flat-config used by every worker host.
// Committed to the repo for auditability (IP-009 Q8); the Dockerfile COPYs this
// to /opt/baseline-eslint.config.mjs where oss_profanity/analyzers/_eslint.py
// expects to find it (--no-config-lookup --config /opt/baseline-eslint.config.mjs).
//
// Pin versions live in the Dockerfile:
//   eslint@10.2.1, @eslint/js@10.0.1, typescript-eslint@8.59.0
// Bumping any of those three changes what `recommended` means — treat this file
// and the Dockerfile pins as one atomic unit.

import js from "@eslint/js";
import tseslint from "typescript-eslint";

export default [
  {
    files: ["**/*.{js,mjs,cjs,jsx,ts,tsx}"],
    ...js.configs.recommended,
  },
  ...tseslint.configs.recommended,
];
