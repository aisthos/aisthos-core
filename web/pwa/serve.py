"""
Простой HTTP-сервер для PWA.
Запуск: python serve.py
Доступ: http://100.109.150.41:8080 (через Tailscale)
"""

import http.server
import os

PORT = 8080
DIR = os.path.dirname(os.path.abspath(__file__))

os.chdir(DIR)

handler = http.server.SimpleHTTPRequestHandler
handler.extensions_map.update({
    '.js': 'application/javascript',
    '.json': 'application/json',
    '.webp': 'image/webp',
    '.png': 'image/png',
})

print(f"AisthOS PWA server: http://0.0.0.0:{PORT}")
print(f"Tailscale: http://100.109.150.41:{PORT}")
print(f"Файлы: {DIR}")

with http.server.HTTPServer(("0.0.0.0", PORT), handler) as httpd:
    httpd.serve_forever()
