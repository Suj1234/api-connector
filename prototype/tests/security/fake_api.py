"""A tiny HTTPS API for sandbox tests, run inside a container as api.example.com."""

import json
import ssl
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.headers.get("Authorization") != "Bearer sandbox-secret-token-42":
            self.send_response(401)
            self.end_headers()
            return
        users = [{"id": i, "email": f"user{i}@acme.example", "last_seen": "2026-10-20T00:00:00Z"} for i in range(1, 4)]
        nxt = "https://evil.example.net/steal" if "evil" in self.path else None
        body = json.dumps({"data": users, "next": nxt}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        pass


server = HTTPServer(("0.0.0.0", 443), Handler)
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain("/srv/cert.pem", "/srv/key.pem")
server.socket = context.wrap_socket(server.socket, server_side=True)
server.serve_forever()
