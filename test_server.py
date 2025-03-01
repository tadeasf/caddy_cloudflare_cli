#!/usr/bin/env python3
"""
Simple HTTP server for health checks with two endpoints:
- /health - returns a health check HTML page
- / - returns a simple Hello World HTML page
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import argparse
import sys
import signal

class SimpleHealthHandler(BaseHTTPRequestHandler):
    """HTTP request handler for simple health checks"""
    
    def do_GET(self):
        """Handle GET requests"""
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            
            html_content = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Health Check</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 40px; }
                    .status { padding: 20px; border-radius: 5px; }
                    .healthy { background-color: #dff0d8; color: #3c763d; }
                </style>
            </head>
            <body>
                <h1>Service Health</h1>
                <div class="status healthy">
                    <h2>Status: Healthy</h2>
                    <p>The service is running normally.</p>
                </div>
            </body>
            </html>
            """
            self.wfile.write(html_content.encode())
            return
        
        elif self.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            
            html_content = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Hello World</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 40px; text-align: center; }
                    h1 { color: #333; }
                </style>
            </head>
            <body>
                <h1>Hello World!</h1>
                <p>Welcome to the simple health check server.</p>
            </body>
            </html>
            """
            self.wfile.write(html_content.encode())
            return
            
        # Default 404 response for any other path
        self.send_response(404)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"<html><body><h1>404 Not Found</h1></body></html>")

def run_server(host="0.0.0.0", port=8080):
    """Run the health check server"""
    server = HTTPServer((host, port), SimpleHealthHandler)
    print(f"Starting health check server on http://{host}:{port}")
    print(f"- Health check: http://{host}:{port}/health")
    print(f"- Hello World: http://{host}:{port}/")
    print("Press Ctrl+C to stop the server")
    
    # Handle graceful shutdown on SIGINT (Ctrl+C)
    def signal_handler(sig, frame):
        print("\nShutting down server...")
        server.shutdown()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        print("Server stopped")

def main():
    """Parse arguments and start the server"""
    parser = argparse.ArgumentParser(description="Simple health check HTTP server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8081, help="Port to bind to (default: 8080)")
    
    args = parser.parse_args()
    run_server(args.host, args.port)

if __name__ == "__main__":
    main()