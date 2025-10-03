#!/bin/bash

# Crea crontab per esecuzione ogni ora
echo "0 * * * * cd /app && python bot_games_hourly_it.py" | crontab -

# Avvia cron
cron

# Test iniziale
python bot_games_hourly_it.py

# Health check server semplice
python -c "
import http.server
import socketserver
import threading
from http.server import BaseHTTPRequestHandler

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'ok')
    def log_message(self, format, *args):
        return

PORT = 8080
Handler = HealthHandler

with socketserver.TCPServer(('', PORT), Handler) as httpd:
    print(f'Health check server at port {PORT}')
    httpd.serve_forever()
"