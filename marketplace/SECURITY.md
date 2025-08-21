# Security

- CI/CD uses Workload Identity Federation; no static service account keys.
- Relay SSRF protections and rate limits.
- JWKS rotation and cache TTL configurable on the Gateway.
- Recommendations:
  - Use separate projects for CI and Production, least-privilege IAM.
  - Prefer authenticated Cloud Run; expose only necessary endpoints.
