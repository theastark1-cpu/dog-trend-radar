#!/usr/bin/env python3
"""HTTP server for the Dog Trend Radar dashboard."""
import http.server
import socketserver
import os

PORT = 8898
DIR = os.path.dirname(os.path.abspath(__file__))

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIR, **kwargs)

    def log_message(self, format, *args):
        pass  # Silent

if __name__ == "__main__":
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"🐕 Dog Trend Radar → http://localhost:{PORT}/dashboard.html")
        print("   Press Ctrl+C to stop")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n✓ Server stopped")
