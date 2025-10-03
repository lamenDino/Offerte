#!/bin/bash

# Crea crontab per esecuzione settimanale (ogni giovedì alle 18:00)
echo "0 18 * * 4 cd /app && python bot_games_channel.py" | crontab -

# Avvia cron
cron

# Test iniziale
python bot_games_channel.py

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