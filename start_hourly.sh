#!/bin/bash

# Avvia cron in background
service cron start

# Configura crontab per esecuzione ogni ora
echo "0 * * * * cd /app && /usr/local/bin/python bot_games_hourly_it.py >> /var/log/cron.log 2>&1" | crontab -

# Verifica che crontab sia configurato
echo "Crontab configurato:"
crontab -l

# Test iniziale
echo "Eseguendo test iniziale..."
python bot_games_hourly_it.py

# Crea file di log per cron
touch /var/log/cron.log

# Health check server che mantiene il container attivo
echo "Avviando health check server sulla porta 8080..."
python3 -c "
import http.server
import socketserver
import threading
import subprocess
import time
from http.server import BaseHTTPRequestHandler

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Bot games server is running')
        elif self.path == '/logs':
            try:
                with open('/var/log/cron.log', 'r') as f:
                    logs = f.read()
                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(logs.encode())
            except:
                self.send_response(404)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        return  # Silenzioso

PORT = 8080
Handler = HealthHandler

print(f'Health check server attivo sulla porta {PORT}')
print('Endpoints disponibili:')
print('  / - Status check')  
print('  /logs - Visualizza log cron')

with socketserver.TCPServer(('', PORT), Handler) as httpd:
    httpd.serve_forever()
"