import json
import sys
from typing import Any, Dict, List, Optional

from abstralix.core.dag import DAGResolver
from abstralix.core.ir import IRBuilder
from abstralix.core.lexer import Lexer
from abstralix.core.parser import Parser
from abstralix.core.schema import ATTRIBUTE_RULES, OBJECT_RULES
from abstralix.errors import AbstralixError


class AbstralixLanguageServer:
    def __init__(self):
        self.documents: Dict[str, str] = {}

    def run(self):
        """Главный цикл чтения сообщений JSON-RPC из stdin и отправки в stdout."""
        while True:
            try:
                line = sys.stdin.buffer.readline()
                if not line:
                    break
                line_str = line.decode("latin1")
                if not line_str.startswith("Content-Length:"):
                    continue

                length = int(line_str.split(":")[1].strip())
                while True:
                    empty = sys.stdin.buffer.readline().decode("latin1")
                    if empty in ("\r\n", "\n", ""):
                        break

                body = sys.stdin.buffer.read(length).decode("utf-8")
                request = json.loads(body)
                self._handle_message(request)
            except Exception:
                pass

    def _send(self, payload: Dict[str, Any]):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("latin1")
        sys.stdout.buffer.write(header + body)
        sys.stdout.buffer.flush()

    def _handle_message(self, req: Dict[str, Any]):
        method = req.get("method")
        msg_id = req.get("id")

        if method == "initialize":
            self._send({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "capabilities": {
                        "textDocumentSync": 1,
                        "hoverProvider": True,
                    }
                }
            })
            return

        if method == "textDocument/didOpen":
            doc = req["params"]["textDocument"]
            uri = doc["uri"]
            self.documents[uri] = doc["text"]
            self._validate_document(uri, doc["text"])
            return

        if method == "textDocument/didChange":
            uri = req["params"]["textDocument"]["uri"]
            text = req["params"]["contentChanges"][0]["text"]
            self.documents[uri] = text
            self._validate_document(uri, text)
            return

        if method == "textDocument/hover":
            uri = req["params"]["textDocument"]["uri"]
            pos = req["params"]["position"]
            text = self.documents.get(uri, "")
            hover_content = self._get_hover(text, pos["line"], pos["character"])
            self._send({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"contents": {"kind": "markdown", "value": hover_content}} if hover_content else None
            })
            return

        if msg_id is not None:
            self._send({"jsonrpc": "2.0", "id": msg_id, "result": None})

    def _validate_document(self, uri: str, text: str):
        diagnostics: List[Dict[str, Any]] = []
        try:
            tokens = Lexer(text, uri).tokenize()
            ast = Parser(tokens, uri).parse()
            ir = IRBuilder().build(ast)
            DAGResolver(ir).resolve_all()
        except AbstralixError as err:
            loc = err.location
            line = max(0, (loc.line - 1) if loc else 0)
            col = max(0, (loc.column - 1) if loc else 0)
            length = loc.length if loc else 1

            diagnostics.append({
                "range": {
                    "start": {"line": line, "character": col},
                    "end": {"line": line, "character": col + length},
                },
                "severity": 1,
                "code": err.code,
                "source": "abstralix",
                "message": f"[{err.code}] {err.message}" + (f"\nHint: {err.hint}" if err.hint else ""),
            })
        except Exception as exc:
            diagnostics.append({
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 0, "character": 1},
                },
                "severity": 1,
                "source": "abstralix",
                "message": str(exc),
            })

        self._send({
            "jsonrpc": "2.0",
            "method": "textDocument/publishDiagnostics",
            "params": {
                "uri": uri,
                "diagnostics": diagnostics,
            }
        })

    def _get_hover(self, text: str, line_no: int, col_no: int) -> Optional[str]:
        lines = text.splitlines()
        if line_no >= len(lines):
            return None
        line = lines[line_no]

        # Извлекаем слово под курсором
        start = col_no
        while start > 0 and (line[start - 1].isalnum() or line[start - 1] in ("@", "_", "-", ".")):
            start -= 1
        end = col_no
        while end < len(line) and (line[end].isalnum() or line[end] in ("@", "_", "-", ".")):
            end += 1

        word = line[start:end]

        if word in ATTRIBUTE_RULES:
            attr = ATTRIBUTE_RULES[word]
            return (
                f"### Attribute `{attr.name}`\n\n"
                f"- **Allowed in:** `{', '.join(attr.allowed_scopes)}`\n"
                f"- **Types:** `{', '.join(attr.allowed_types)}`\n"
                f"- **Inheritable:** `{attr.inheritable}`\n"
                f"- **Default:** `{attr.default!r}`\n"
            )

        if word in OBJECT_RULES:
            obj = OBJECT_RULES[word]
            return (
                f"### Object `{obj.name}`\n\n"
                f"- **Allowed inside:** `{', '.join(obj.allowed_parents)}`\n"
                f"- **Can contain:** `{', '.join(obj.can_contain) or 'Atomic leaf (no children)'}`\n"
            )

        return None