# Security Policy

## Supported versions

Only the latest release on the [Releases page](https://github.com/Dozer3530/Perch/releases)
is supported. Older versions will not receive fixes.

## Threat model

Perch is a local Windows desktop app. It:

- Reads files from a source folder you choose.
- Writes files to a destination folder you choose.
- Makes one outbound HTTPS call per launch to `api.github.com` to check the
  latest release version (read-only, no authentication, cached for 24 hours).

It does not open network listeners, does not transmit your imagery, and does
not run code it downloads.

## Reporting a vulnerability

Please report security issues privately using GitHub's private vulnerability
reporting:

https://github.com/Dozer3530/Perch/security/advisories/new

Please do not open a public issue for a security problem.

Include:

- The Perch version (visible in the window title or `perch/__init__.py`).
- Your Windows version.
- Steps to reproduce.
- The impact you observed or believe is possible.

A response is aimed for within a few business days. Fixes ship via the normal
release workflow (a new `v*` tag triggers a signed-by-no-one-but-built-by-CI
`Perch.exe` on the Releases page).
