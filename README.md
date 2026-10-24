# TizenTube Personal

Personal, version-pinned deployment for Samsung QN55LS03BAFXZC (Tizen 6.5).

## Changes

- Own CDN: `https://dearlordylord.github.io/tizentube-personal/cdn/userScript-1.15.2-7a092351e0e3.js`.
- The TV downloads the fixed 1.15.2 script over verified HTTPS, checks SHA-256 against the manifest embedded in the signed app, and only then serves it to YouTube from a local route. A replaced file, redirect, oversized response, timeout or failed request cannot supply executable code. There is no fallback to the author's CDN.
- The Cobalt proxy binds only `127.0.0.2:8101`, matching the existing Cobalt proxy setting. The legacy HTTP service remains on `127.0.0.1:8100`.
- All three standalone script-loading paths use the verified local route, including the legacy debugger path.
- Existing package/application IDs are retained so installation updates the same tile and preserves app data. Display name is TizenTube Personal, package version 2.1.2.

## Scope

Only the TizenTube extension script is fixed. YouTube's own site/player code still comes from Google. SponsorBlock and DeArrow retain upstream behavior and optional external requests. This change does not claim a complete firmware, native Cobalt, or transitive-dependency audit.

The proxy runs on the TV. It modifies the YouTube page locally to insert the extension. It does not route the TV's traffic through an author's remote proxy. Its app-specific TLS CA is used by a private Cobalt content copy; no system-wide CA is installed by the reviewed setup code.

## Build and check

```sh
python3 build-package.py
node tests/loader.cjs
python3 tests/package.py
```

The builder downloads only the upstream 2.1.1 WGT whose SHA-256 is embedded in the builder. It patches the already-shipped bundle and matching source; it does not install npm packages or execute upstream build scripts. The result is unsigned and must be signed with a Samsung certificate for the target TV. Signed packages, certificates, account tokens and private device identifiers are excluded from this repository.

## Source and license

GPL-3.0-only. Original TizenTube copyright remains with its authors. See LICENSE, NOTICE.txt and patches/upstream.diff. Full corresponding first-party source snapshots are in source/:

- WGT source: reisxd/TizenTube v2.1.1, commit 893b663d35efa558d8bdf9f54f0c4f9a31ab6a07.
- Script source: @foxreis/tizentube 1.15.2, commit f99945a84ff767bf14ad8c1146e8e3fd49a3d628.

The script is an unchanged copy of npm's 1.15.2 distribution, verified against npm's published SHA-512 archive integrity and against the live CDN copy during review. Its SHA-256 is 7a092351e0e348507ef9c97da8833d5f6717de628517f5299053b3c2073f1d69. New script bytes require an explicit manifest/app update; editing CDN contents alone cannot change what executes.
