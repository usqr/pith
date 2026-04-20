# Security Policy

## Supported versions

Pith installs Claude Code hooks that run on every session, every prompt, and
every tool call with the user's local privileges. Security issues are taken
seriously regardless of severity.

Only the `main` branch is supported. Fixes land there first and are then cut
into tagged releases.

## Reporting a vulnerability

**Please do not open a public issue for security reports.** Use GitHub's
private advisory flow instead:

1. Go to https://github.com/abhisekjha/pith/security/advisories/new
2. Fill in the template — reproduction steps, affected files, suspected
   severity, and (if possible) a suggested fix.
3. You'll get an acknowledgement within 3 business days.

If GitHub's advisory form isn't practical, email the maintainer listed in the
repo's root `README.md`. PGP is not required but is welcome.

## What to expect

- Acknowledgement within 3 business days.
- Triage + severity call within 7 business days.
- Fix target: HIGH within 14 days; MODERATE within 30 days; LOW with the
  next scheduled release.
- You'll be credited in the release notes unless you prefer otherwise.

## Out of scope

- Findings that require an already-compromised local account
  (hook files in `~/.claude/hooks/pith/` can be tampered with by any process
  running as the user — that's a given of the execution model).
- DoS against an individual session (hooks already time out at ≤10 s).
- Purely cosmetic issues in telemetry or statusline output.

## Pinned installs

When the installer runs with `PITH_REF=vX.Y.Z` and `PITH_PIN_SHA=…` set, it
refuses to install if the resolved HEAD doesn't match the expected SHA. With
`PITH_VERIFY_GPG=1`, it additionally requires the tag to carry a valid GPG
signature. These options are documented in `install.sh --help`.

## Telemetry

Pith keeps a local-only log at `~/.pith/telemetry.jsonl` containing counts
and ratios. When `PITH_TELEMETRY_VERBOSE=1` is set, the first three lines
of every tool output are additionally stored — with secret-shape redaction
applied. The file auto-rotates at ~10 MiB. If you want to inspect or clear
it: `/pith telemetry` and `/pith telemetry purge`. Scrub before sharing.
