#!/usr/bin/env python3
"""
Dashboard HTTP Server
Serves the SuperAgent dashboard with screenshots over HTTP.
"""
import http.server
import socketserver
import os
import json
from pathlib import Path
from urllib.parse import urlparse, parse_qs

PORT = 8080
DASHBOARD_DIR = Path(__file__).parent
ARTIFACTS_DIR = DASHBOARD_DIR / 'artifacts'


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    """Custom handler for dashboard with CORS and proper content types."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DASHBOARD_DIR), **kwargs)

    def end_headers(self):
        """Add CORS headers to allow WebSocket connections."""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()

    def do_GET(self):
        """Handle GET requests with custom routing."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        # Serve dashboard at root
        if path == '/' or path == '/index.html':
            self.path = '/dashboard.html'
            return super().do_GET()

        # Serve artifacts (screenshots, videos, traces)
        if path.startswith('/artifacts/'):
            # Remove /artifacts/ prefix and serve from artifacts directory
            artifact_path = ARTIFACTS_DIR / path[11:]  # Remove '/artifacts/'

            if artifact_path.exists() and artifact_path.is_file():
                self.send_response(200)

                # Set content type based on file extension
                if path.endswith('.png'):
                    self.send_header('Content-Type', 'image/png')
                elif path.endswith('.jpg') or path.endswith('.jpeg'):
                    self.send_header('Content-Type', 'image/jpeg')
                elif path.endswith('.mp4'):
                    self.send_header('Content-Type', 'video/mp4')
                elif path.endswith('.json'):
                    self.send_header('Content-Type', 'application/json')
                else:
                    self.send_header('Content-Type', 'application/octet-stream')

                self.end_headers()

                # Send file contents
                with open(artifact_path, 'rb') as f:
                    self.wfile.write(f.read())
                return
            else:
                self.send_error(404, f"Artifact not found: {path}")
                return

        # Serve API endpoint for listing screenshots
        if path == '/api/screenshots':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()

            # Find all screenshots in artifacts directory
            screenshots = []
            if ARTIFACTS_DIR.exists():
                for png_file in ARTIFACTS_DIR.rglob('*.png'):
                    rel_path = png_file.relative_to(ARTIFACTS_DIR)
                    screenshots.append({
                        'path': f'/artifacts/{rel_path}',
                        'name': png_file.name,
                        'test': png_file.parent.name,
                        'modified': png_file.stat().st_mtime
                    })

            # Sort by modification time (newest first)
            screenshots.sort(key=lambda x: x['modified'], reverse=True)

            response = json.dumps(screenshots)
            self.wfile.write(response.encode())
            return

        # Default: serve static files
        return super().do_GET()

    def log_message(self, format, *args):
        """Custom log format."""
        print(f"[Dashboard] {self.address_string()} - {format % args}")


def main():
    """Start the dashboard server."""
    # Ensure artifacts directory exists
    ARTIFACTS_DIR.mkdir(exist_ok=True)

    # Create server
    with socketserver.TCPServer(("", PORT), DashboardHandler) as httpd:
        print(f"""
╔══════════════════════════════════════════════════════════════╗
║           SuperAgent Dashboard Server                         ║
╚══════════════════════════════════════════════════════════════╝

✅ Server started successfully!

📊 Dashboard:    http://localhost:{PORT}
🌐 WebSocket:    ws://localhost:3010/agent-events
📁 Artifacts:    {ARTIFACTS_DIR}

Open your browser to: http://localhost:{PORT}

Press Ctrl+C to stop the server.
""")

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\n👋 Shutting down dashboard server...")
            httpd.shutdown()


if __name__ == '__main__':
    main()
