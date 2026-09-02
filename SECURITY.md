# Security policy

This repository contains an open-source research workflow, not a production or
safety-critical service.

## Supported version

Security fixes are applied to the latest revision of the default branch. No
older release line is currently maintained.

## Reporting a vulnerability or sensitive disclosure

Use GitHub's private vulnerability reporting for this repository if it is
enabled. If it is unavailable, contact the maintainer through the private
contact method listed on the maintainer's GitHub profile. Do not publish
credentials, personal data, unpublished research material, or working exploit
details in a public issue.

Please include:

- the affected file or component;
- the impact and conditions required to reproduce it;
- minimal reproduction steps using synthetic data; and
- any suggested mitigation.

The maintainer will acknowledge a complete report when practical, assess its
scope, and coordinate a fix or disclosure. This small open-source project does
not promise a formal response-time service level.

## Scope notes

Particularly useful reports include:

- accidental inclusion of a secret, personal datum, local path, or private
  research artifact;
- unsafe path handling or unintended file access in the demo;
- dependency vulnerabilities that are reachable through the included code; or
- a test or verifier that can be bypassed while producing an accepted decision.

Incorrect scientific conclusions without a security impact should be reported
as ordinary reproducibility issues, with no private data attached.
