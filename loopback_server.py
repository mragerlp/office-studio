"""Numeric loopback HTTP binding without startup reverse-DNS requests."""
from http.server import ThreadingHTTPServer
from socketserver import TCPServer


class LoopbackHTTPServer(ThreadingHTTPServer):
    def server_bind(self):
        # HTTPServer otherwise calls socket.getfqdn(), which can block local
        # startup on macOS. This numeric local address needs no DNS identity.
        TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]
