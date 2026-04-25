// IP-013: build-time canary. Lint-clean under the baseline config so
// `eslint canary.js` exits 0 on success; any non-zero exit means the
// flat-config could not load (the bug this proposal fixes).
export const ok = 1;
