from __future__ import annotations

import base64
import binascii
import json
import tempfile
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from pdf_processor import convert_pdf_to_markdown

PORT = 8765


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # silence request logs

    def do_GET(self):
        if self.path != "/":
            self.send_error(404)
            return
        html = (Path(__file__).parent / "index.html").read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)

    def do_POST(self):
        if self.path != "/convert":
            self._send_json(404, {"error": "Not found"})
            return

        try:
            payload = self._read_json_body()
            encoded_pdf = payload["data"]
            filename = payload.get("filename", "document.pdf")
            pdf_bytes = base64.b64decode(encoded_pdf, validate=True)
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError, KeyError, TypeError, binascii.Error) as exc:
            self._send_json(400, {"error": f"Invalid request: {exc}"})
            return

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name

        try:
            markdown = convert_pdf_to_markdown(tmp_path, title=Path(filename).stem)
        except Exception as exc:
            self._send_json(500, {"error": f"Conversion failed: {exc}"})
            return
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        self._send_json(200, {"markdown": markdown, "filename": Path(filename).stem + ".md"})

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        return json.loads(body)

    def _send_json(self, status_code: int, payload: dict):
        data = json.dumps(payload).encode()
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)


def main():
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://127.0.0.1:{PORT}"
    print(f"PDF to Markdown running at {url}")
    threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
