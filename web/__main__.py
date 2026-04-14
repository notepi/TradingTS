import argparse
from web.dashboard import serve_dashboard

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TradingAgents Dashboard")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind to")
    args = parser.parse_args()
    serve_dashboard(host=args.host, port=args.port)
