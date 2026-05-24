"""
app/dashboard/nlp_dashboard.py
=====================================
Serveur HTML — TuniState Métriques NLP
Sert dashboard_nlp.html sur http://localhost:8050
Même structure que metrics_dashboard.py
"""
import os
import sys
import http.server
 
# Chemin vers le fichier HTML dans frontend/
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HTML_FILE = os.path.join(BASE_DIR, "frontend", "dashboard_nlp.html")
 
 
class NLPDashboardHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            with open(HTML_FILE, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_error(404, f"dashboard_nlp.html introuvable dans {BASE_DIR}")
 
    def log_message(self, format, *args):
        pass  # silence les logs HTTP
 
 
if __name__ == "__main__":
    port = int(os.getenv("DASHBOARD_PORT", "8050"))
    server = http.server.HTTPServer(("0.0.0.0", port), NLPDashboardHandler)
    print(f"Dashboard: http://localhost:{port}")
    server.serve_forever()