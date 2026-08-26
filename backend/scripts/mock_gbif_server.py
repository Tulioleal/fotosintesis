import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/health":
            self._send({"status": "ok"})
            return

        if parsed.path == "/v1/species/suggest":
            self._handle_suggest(parsed)
            return

        if parsed.path != "/v1/species/match":
            self.send_error(404)
            return

        name = parse_qs(parsed.query).get("name", [""])[0]
        if name.casefold() != "cotyledon tomentosa":
            self._send({"matchType": "NONE", "confidence": 0})
            return

        self._send({
            "usageKey": 4219524,
            "acceptedUsageKey": 4219524,
            "scientificName": "Cotyledon tomentosa Harv.",
            "acceptedScientificName": "Cotyledon tomentosa Harv.",
            "canonicalName": "Cotyledon tomentosa",
            "status": "ACCEPTED",
            "matchType": "EXACT",
            "confidence": 100,
            "synonym": False,
            "genus": "Cotyledon",
            "family": "Crassulaceae",
            "species": "Cotyledon tomentosa",
        })

    def _handle_suggest(self, parsed: "urlparse.ParseResult") -> None:
        query = parse_qs(parsed.query).get("q", [""])[0].casefold()
        if "cotyledon" not in query and "tomentosa" not in query:
            self._send([])
            return
        self._send([
            {
                "key": 4219524,
                "acceptedKey": 4219524,
                "scientificName": "Cotyledon tomentosa Harv.",
                "acceptedName": "Cotyledon tomentosa Harv.",
                "canonicalName": "Cotyledon tomentosa",
                "status": "ACCEPTED",
                "rank": "SPECIES",
                "genus": "Cotyledon",
                "family": "Crassulaceae",
                "species": "Cotyledon tomentosa",
            },
            {
                "key": 4219525,
                "acceptedKey": 4219525,
                "scientificName": "Cotyledon orbiculata",
                "acceptedName": "Cotyledon orbiculata",
                "canonicalName": "Cotyledon orbiculata",
                "status": "ACCEPTED",
                "rank": "SPECIES",
                "genus": "Cotyledon",
                "family": "Crassulaceae",
                "species": "Cotyledon orbiculata",
            },
        ])

    def _send(self, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
