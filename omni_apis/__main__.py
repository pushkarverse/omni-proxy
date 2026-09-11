"""Entry point: python -m omni_proxy"""
import argparse
import os

from .config import CONFIG, load_config, find_config
from .models import MODELS
from .gemini import HAS_HTTPX
from . import __version__


def main():
    parser = argparse.ArgumentParser(description="Gemini to OpenAI-compatible API proxy")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--config", type=str, default=None)
    parser.add_argument("--cookie-file", type=str, default=None)
    parser.add_argument("--proxy", type=str, default=None, help="HTTP proxy, e.g. http://127.0.0.1:7890")
    parser.add_argument("--version", action="version", version=f"omni-proxy {__version__}")
    args = parser.parse_args()

    config_path = args.config or os.environ.get("OMNI_PROXY_CONFIG") or find_config()
    if config_path:
        load_config(config_path)

    if args.port:
        CONFIG["port"] = args.port
    if args.cookie_file:
        CONFIG["cookie_file"] = args.cookie_file
    if args.proxy:
        CONFIG["proxy"] = args.proxy

    port = CONFIG["port"]
    print(f"omni-proxy v{__version__}")
    print(f"  Listening: http://0.0.0.0:{port}")
    print(f"  Base URL:  http://localhost:{port}/v1")
    all_models = [m for provider in MODELS.values() for m in provider.keys()]
    print(f"  Models:    {', '.join(all_models)}")
    print(f"  Cookie:    {'yes' if CONFIG.get('cookie_file') else 'none (anonymous)'}")
    print(f"  Proxy:     {CONFIG.get('proxy') or 'system env'}")
    print(f"  Streaming: {'httpx (true streaming)' if HAS_HTTPX else 'urllib (buffered)'}")
    print(f"  Temporary: {'yes' if CONFIG.get('temporary_chats', False) else 'no'}")
    print()
    try:
        import uvicorn
        uvicorn.run("omni_apis.api:app", host=CONFIG["host"], port=port)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
