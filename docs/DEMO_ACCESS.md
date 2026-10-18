# Demo Access Control

Demo access control, not production security. A real deployment would use SSO or on-prem identity, audit logging and encrypted storage.

## Demo Credentials

| Role | Username | Password | Accessible Pages |
|---|---|---|---|
| Viewer | `viewer` | `vd_viewer_2026` | Fleet Overview, Aircraft Detail, Results, Methodology |
| Maintainer | `maintainer` | `vd_maintainer_2026` | Viewer pages + Digital Twin, Planner |
| Administrator | `admin` | `vd_admin_2026` | All pages (Everything) |

## Implementation Notes
- Passwords are stored in `app/auth.py` strictly as SHA-256 digests (`DEMO_USERS`).
- Verification is performed using `hmac.compare_digest` for constant-time comparison.
- Default unauthenticated access uses `GUEST_ROLE = "viewer"`.
