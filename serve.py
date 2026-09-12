#!/usr/bin/env python3
"""Log cleanup and HTTP server for spur results"""

import os
import time
import subprocess
import json
import http.server
import socketserver
from http.server import ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

# Load .env automatically if present
_dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.isfile(_dotenv_path):
    with open(_dotenv_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                if k not in os.environ:
                    os.environ[k] = v

PORT = int(os.environ.get("PORT", "8765"))
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")

os.makedirs(LOG_DIR, exist_ok=True)

def cleanup_old_logs():
    """Delete log files older than 15 minutes"""
    now = time.time()
    for filename in os.listdir(LOG_DIR):
        filepath = os.path.join(LOG_DIR, filename)
        if os.path.isfile(filepath):
            file_time = os.path.getmtime(filepath)
            if now - file_time > 15 * 60:
                os.remove(filepath)
                print(f"[LOG CLEANUP] Removed: {filename}")

def log_to_file(message):
    """Append log to file with timestamp"""
    with open(f"{LOG_DIR}/access.log", "a") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")

class RequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        # API endpoint for generating a session
        if path.startswith("/api/session"):
            self.handle_api_session(parsed)
            return
            
        cleanup_old_logs()
        log_to_file(f"GET {self.path}")
        super().do_GET()
    
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == "/api/save_log":
            self.handle_save_log()
            return
        
        if path == "/api/session":
            self.handle_api_session(parsed)
            return
            
        self.send_error(405, "Method Not Allowed")
    
    def handle_api_session(self, parsed):
        """Handle API request to generate a single session"""
        query = parse_qs(parsed.query)
        country = query.get("country", [""])[0] or "jp"
        city = query.get("city", [""])[0] or ""
        lifetime = query.get("lifetime", ["15m"])[0]
        
        # Generate session ID
        import random
        sid = ''.join(random.choice('0123456789abcdef') for _ in range(8))
        
        # Build password (credentials loaded from environment)
        base_pass = os.environ.get("IPROYAL_PASSWORD", "DEFAULT")
        username = os.environ.get("IPROYAL_USERNAME", "DEFAULT")
        host = os.environ.get("IPROYAL_HOST", "geo.iproyal.com")
        port = os.environ.get("IPROYAL_PORT", "11203")
        
        pass_parts = [base_pass]
        if country:
            pass_parts.append(f"country-{country}")
        if city:
            pass_parts.append(f"city-{city}")
        pass_parts.append(f"session-{sid}")
        pass_parts.append(f"lifetime-{lifetime}")
        password = "_".join(pass_parts)
        
        proxy_url = f"http://{username}:{password}@{host}:{port}"
        
        # Run curl
        import time
        start_time = time.time()
        cmd = [
            "curl", "-s", "-x", proxy_url,
            "-L", "https://ipctx.me/json",
            "--max-time", "15"
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            if result.returncode == 0 and result.stdout.strip():
                try:
                    data = json.loads(result.stdout)
                    response_data = {
                        "success": True,
                        "session_id": sid,
                        "password": password,
                        "data": data,
                        "proxies": data.get("client", {}).get("proxies", []),
                        "risks": data.get("risks", []),
                        "tunnels": data.get("tunnels", []),
                        "ms": time.time() - start_time
                    }
                    self.send_json_response(response_data)
                except json.JSONDecodeError:
                    self.send_error(500, "Invalid JSON response from ipctx.me")
            else:
                self.send_error(502, f"Proxy error: {result.stderr}")
        except subprocess.TimeoutExpired:
            self.send_error(504, "Request timeout")
        except Exception as e:
            self.send_error(500, f"Internal error: {str(e)}")
    
    def handle_save_log(self):
        """Save clean session results to a log file"""
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            data = json.loads(body.decode())
            
            # Generate random filename
            import random
            sid = ''.join(random.choice('0123456789abcdef') for _ in range(8))
            filename = f"results_{sid}.jsonl"
            filepath = os.path.join(LOG_DIR, filename)
            
            # Write JSONL
            with open(filepath, 'w') as f:
                for item in data:
                    f.write(json.dumps(item) + '\n')
            
            self.send_json_response({"success": True, "filename": filename})
        except Exception as e:
            self.send_error(500, f"Save log error: {str(e)}")
    
    def send_json_response(self, data):
        """Send JSON response"""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def log_message(self, format, *args):
        """Log to file with timestamp"""
        message = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {format % args}"
        with open(LOG_DIR + "/server.log", "a") as f:
            f.write(message + "\n")
        # Also print to console for visibility
        print(message)

def log_to_file(message):
    """Append log to file with timestamp"""
    with open(f"{LOG_DIR}/access.log", "a") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")

# Main server setup
with ThreadingHTTPServer(("", PORT), RequestHandler) as httpd:
    print(f"Serving at http://localhost:{PORT}/")
    print(f"Log dir: {LOG_DIR}")
    print("Press Ctrl+C to stop")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")