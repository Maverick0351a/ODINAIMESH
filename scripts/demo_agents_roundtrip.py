import os, sys, json
import httpx

GATEWAY = os.environ.get("ODIN_GATEWAY_URL", "http://127.0.0.1:7070")
BETA_URL = os.environ.get("AGENT_BETA_URL", "http://127.0.0.1:9090/task")


def post_json(url, obj):
    r = httpx.post(url, json=obj, timeout=30.0)
    r.raise_for_status()
    ct = r.headers.get("content-type", "")
    if "application/json" in ct:
        return r.json(), r
    return None, r


def envelope(payload):
    data, resp = post_json(f"{GATEWAY}/v1/envelope", payload)
    return data


def enforced_translate(payload, from_sft, to_sft, map_name):
    tr = {"payload": payload, "from_sft": from_sft, "to_sft": to_sft, "map": map_name}
    env = envelope(tr)
    data, resp = post_json(f"{GATEWAY}/v1/translate", env)
    if isinstance(data, dict) and "payload" in data and "sft" in data:
        return data["payload"], data, resp
    return data, None, resp


def main():
    print(f"GATEWAY={GATEWAY}\nBETA_URL={BETA_URL}")

    alpha_req = {"intent": "alpha.ask", "ask": "what is 2+2?", "reason": "demo"}
    print("\n[Alpha → Beta] translating request...")
    beta_req, env1, resp1 = enforced_translate(alpha_req, "alpha@v1", "beta@v1", "alpha@v1__beta@v1")
    print("  beta_req:", json.dumps(beta_req, indent=2))

    print("\n[Agent Beta] executing task...")
    beta_reply, _ = post_json(BETA_URL, beta_req)
    print("  beta_reply:", json.dumps(beta_reply, indent=2))

    print("\n[Beta → Alpha] translating result...")
    alpha_res, env2, resp2 = enforced_translate(beta_reply, "beta@v1", "alpha@v1", "beta@v1__alpha@v1")
    print("  alpha_result:", json.dumps(alpha_res, indent=2))

    print("\n[HEL] attempting a denied intent (alpha.delete)...")
    bad_alpha = {"intent": "alpha.delete", "target": "/tmp/secret"}
    try:
        _, _, _ = enforced_translate(bad_alpha, "alpha@v1", "beta@v1", "alpha@v1__beta@v1")
        print("  UNEXPECTED: request was not blocked")
    except httpx.HTTPStatusError as e:
        print(f"  BLOCKED as expected: HTTP {e.response.status_code}")
        try:
            print("  detail:", e.response.json())
        except Exception:
            print("  raw:", e.response.text)


if __name__ == "__main__":
    try:
        main()
    except httpx.HTTPStatusError as e:
        print(f"HTTP error: {e.response.status_code} {e.request.method} {e.request.url}")
        print(e.response.text)
        sys.exit(1)
    except Exception as e:
        print("Error:", e)
        sys.exit(1)
