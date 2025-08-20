# Cloud Armor/WAF Quick Start

This guide shows a minimal path to protect the ODIN Gateway behind Cloud Armor.

## 1) Create a security policy

Example (rate limit and basic path allow-list):

```bash
# Allow specific paths and methods, deny others
gcloud compute security-policies create odin-gateway-waf --description "ODIN Gateway WAF" --project ${PROJECT_ID}

gcloud compute security-policies rules create 1000 \
  --security-policy odin-gateway-waf \
  --expression "in(request.path, ['/metrics','/health','/.well-known/odin/discovery.json','/.well-known/jwks.json']) || starts_with(request.path, '/v1/')" \
  --action allow --project ${PROJECT_ID}

gcloud compute security-policies rules create 2000 \
  --security-policy odin-gateway-waf \
  --action deny-403 --project ${PROJECT_ID}

# Optional: rate limit per client IP
gcloud compute security-policies rules create 1100 \
  --security-policy odin-gateway-waf \
  --expression "true" \
  --action throttle \
  --rate-limit-threshold-count 300 --rate-limit-threshold-interval-sec 60 \
  --enforce-on-key IP \
  --project ${PROJECT_ID}
```

Adjust the allow-list and limits for your org. Add additional deny rules (SQLi/XSS pre-configured rules are available in Cloud Armor WAF).

## 2) Attach policy to Cloud Run service

Create a Serverless NEG for the Cloud Run service via a load balancer, then attach the security policy to the backend service:

```bash
# Create a global external HTTP(S) load balancer for serverless
# (Use console or gcloud run deploy --ingress internal-and-cloud-load-balancing for internal LB)

# Attach policy
gcloud compute backend-services update BACKEND_NAME \
  --security-policy odin-gateway-waf --global --project ${PROJECT_ID}
```

Consult Google’s Serverless NEG + Cloud Armor docs for end-to-end LB steps. For strictly internal access, use "internal-and-cloud-load-balancing" ingress and private IP via PSC.
