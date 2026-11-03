# Security

Report sensitive issues privately to contact@arkadia.solutions with subject "AK-Data security". Include affected version, minimal synthetic reproduction and impact. Do not post credentials, company datasets or private conversations in public issues. An acknowledgement target is three business days; this is not an SLA.

The current version is 0.3.0. Fixes are made on the development branch and released as a new version; there is no promised backport policy for 0.2.x or 0.1.x. macOS release binaries are signed with a Developer ID certificate and notarized by Apple; every release lists SHA-256 checksums (`SHA256SUMS`).

Core encode/decode stays local and provides no encryption or anonymization. Data and metadata from tools are untrusted content, never trusted agent instructions. `make benchmark` is offline by default; `NETWORK=1` explicitly allows dataset/report inputs to reach the selected provider. Reports may retain prompts, answers and paths and are private by default. Never commit `.env`, private daemon state or raw company benchmark reports. Browser playground drafts are saved only when the user opts in; clear saved input on shared devices.

Run `python3 scripts/check_release.py --history` before sharing a commit. Pattern scanning is one release check, not a guarantee that arbitrary confidential content is safe to publish.
