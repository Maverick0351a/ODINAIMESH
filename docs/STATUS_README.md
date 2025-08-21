# ODIN Protocol â€” System Status (auto-generated)

Generated: 2025-08-20T15:54:04Z UTC
Project: odin-producer  |  Region: us-central1

Gateway: 
Relay  : https://odin-relay-2gdlxqcina-uc.a.run.app

## Summary
| Check | Status | HTTP |
|---|---|---|
| Gateway /metrics | âŒ | 0 |
| Relay /metrics | âŒ | 403 |
| Envelope | âŒ | 0 |
| Translate | âŒ | 0 |
| Receipts list | âŒ | 0 |
| Relay httpbin | âŒ | 403 |
| Relay SSRF block | âœ… | 403 |
| Admin reload | âŒ | 0 |

## Artifacts
- Gateway image: us-central1-docker.pkg.dev/odin-producer/odin/gateway:v0.0.1
- Relay image  : us-central1-docker.pkg.dev/odin-producer/odin/relay:v0.0.1
- Release run  : 

## Notes
- Cloud Run services may require auth; 403 indicates auth needed rather than outage.

Footer: Run at 2025-08-20T15:54:04Z UTC; PROJECT_ID=odin-producer; REGION=us-central1
