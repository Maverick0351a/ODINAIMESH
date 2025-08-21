import os
import uvicorn


def main() -> None:
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run("apps.agent_beta.api:app", host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
