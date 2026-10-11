# Scripts

## `rea_capture.sh`

Re-runs the REA capture of driveindex.com: Chromium with a loopback DevTools port, then
`inspect-web-page`, `analyze-web-bundle`, `export-web-scripts` and
`analyze-javascript-application`. Results land in `./capture/`, which is git-ignored because it
holds DriveIndex's own JavaScript.

## Regenerating `tests/fixtures_js_parity.json`

1. Prettify the dashboard chunk: `npx prettier@3.3.3 --parser babel <chunk>.js > dash.pretty.js`.
2. Take lines 19-676 (functions `m`, `x`, `v`, `b`, `S`, `k`), prepend `const l = {env:{}};`
   and append a harness that calls them with seeded-random inputs (LCG seed 12345, 400 cases)
   and writes the JSON fixture.
3. Run `pytest`. The Python port must match every case.

The harness isn't committed because it embeds DriveIndex's code. Only its outputs are.
