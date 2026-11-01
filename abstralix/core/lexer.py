from typing import List
from abstralix.core.tokens import Token, TokenType
from abstralix.errors import SyntaxAbxError, SourceLocation

TRIPLE_QUOTE = '"' * 3


class Lexer:
    """Lexical analyzer transforming .abx source text into a stream of tokens."""

    def __init__(self, source: str, file_path: str = "<memory>"):
        self.source = source
        self.file_path = file_path
        self.pos = 0
        self.line = 1
        self.col = 1
        self.length = len(source)

    def _current(self) -> str:
        if self.pos >= self.length:
            return "\0"
        return self.source[self.pos]

    def _peek(self, offset: int = 1) -> str:
        idx = self.pos + offset
        if idx >= self.length:
            return "\0"
        return self.source[idx]

    def _advance(self, steps: int = 1) -> str:
        result = ""
        for _ in range(steps):
            if self.pos < self.length:
                ch = self.source[self.pos]
                result += ch
                self.pos += 1
                if ch == "\n":
                    self.line += 1
                    self.col = 1
                else:
                    self.col += 1
        return result

    def _loc(self, start_line: int, start_col: int, length: int = 1) -> SourceLocation:
        return SourceLocation(
            file=self.file_path,
            line=start_line,
            column=start_col,
            length=max(1, length),
        )

    def tokenize(self) -> List[Token]:
        tokens: List[Token] = []

        while self.pos < self.length:
            ch = self._current()

            # 1. Skip whitespace and newlines
            if ch.isspace():
                self._advance()
                continue

            # 2. Single-line comments //
            if ch == "/" and self._peek() == "/":
                while self.pos < self.length and self._current() != "\n":
                    self._advance()
                continue

            # 3. Multi-line comments /* ... */
            if ch == "/" and self._peek() == "*":
                start_line, start_col = self.line, self.col
                self._advance(2)
                closed = False
                while self.pos < self.length:
                    if self._current() == "*" and self._peek() == "/":
                        self._advance(2)
                        closed = True
                        break
                    self._advance()
                if not closed:
                    raise SyntaxAbxError(
                        code="SYN_UNCLOSED_LITERAL",
                        message="Unclosed multi-line comment '/*'",
                        location=self._loc(start_line, start_col, 2),
                        hint="Add closing '*/' at the end of the comment block.",
                    )
                continue

            start_line, start_col = self.line, self.col

            # 4. Single-character delimiters
            single_char_tokens = {
                "{": TokenType.LBRACE,
                "}": TokenType.RBRACE,
                "[": TokenType.LBRACKET,
                "]": TokenType.RBRACKET,
                "(": TokenType.LPAREN,
                ")": TokenType.RPAREN,
                ",": TokenType.COMMA,
            }
            if ch in single_char_tokens:
                self._advance()
                tokens.append(
                    Token(
                        type=single_char_tokens[ch],
                        value=ch,
                        raw=ch,
                        location=self._loc(start_line, start_col, 1),
                    )
                )
                continue

            # 5. Assignment operators: =, +=, -=
            if ch == "=":
                self._advance()
                tokens.append(Token(TokenType.ASSIGN, "=", "=", self._loc(start_line, start_col, 1)))
                continue

            if ch == "+" and self._peek() == "=":
                self._advance(2)
                tokens.append(Token(TokenType.PLUS_ASSIGN, "+=", "+=", self._loc(start_line, start_col, 2)))
                continue

            if ch == "-" and self._peek() == "=":
                self._advance(2)
                tokens.append(Token(TokenType.MINUS_ASSIGN, "-=", "-=", self._loc(start_line, start_col, 2)))
                continue

            # 6. String literals
            if ch == '"':
                tokens.append(self._read_string())
                continue

            # 7. Attributes (@)
            if ch == "@":
                tokens.append(self._read_attribute())
                continue

            # 8. Numeric literals
            if ch.isdigit() or (ch == "-" and self._peek().isdigit()):
                tokens.append(self._read_number())
                continue

            # 9. Identifiers (keywords, names with dots for filenames)
            if ch.isalpha() or ch == "_":
                tokens.append(self._read_identifier())
                continue

            raise SyntaxAbxError(
                code="SYN_UNEXPECTED_TOKEN",
                message=f"Unexpected character '{ch}' encountered",
                location=self._loc(start_line, start_col, 1),
                hint="Check syntax rules for Abstralix 0.5.0.",
            )

        tokens.append(
            Token(
                type=TokenType.EOF,
                value=None,
                raw="",
                location=self._loc(self.line, self.col, 1),
            )
        )
        return tokens

    def _read_string(self) -> Token:
        start_line, start_col = self.line, self.col

        # Triple-quoted multi-line string
        if self._peek(1) == '"' and self._peek(2) == '"':
            self._advance(3)
            chars: List[str] = []
            while self.pos < self.length:
                if self._current() == '"' and self._peek(1) == '"' and self._peek(2) == '"':
                    self._advance(3)
                    raw_val = "".join(chars)
                    if raw_val.startswith("\n"):
                        raw_val = raw_val[1:]
                    elif raw_val.startswith("\r\n"):
                        raw_val = raw_val[2:]
                    return Token(
                        type=TokenType.STRING,
                        value=raw_val,
                        raw=f"{TRIPLE_QUOTE}{raw_val}{TRIPLE_QUOTE}",
                        location=self._loc(start_line, start_col, len(raw_val) + 6),
                    )
                chars.append(self._advance())

            raise SyntaxAbxError(
                code="SYN_UNCLOSED_LITERAL",
                message="Unclosed multi-line string literal (expected triple quotes)",
                location=self._loc(start_line, start_col, 3),
                hint="Close the multi-line string with three double quotes.",
            )

        # Single-line string
        self._advance(1)
        chars = []
        while self.pos < self.length:
            ch = self._current()
            if ch == '"':
                self._advance(1)
                val = "".join(chars)
                return Token(
                    type=TokenType.STRING,
                    value=val,
                    raw=f'"{val}"',
                    location=self._loc(start_line, start_col, len(val) + 2),
                )
            if ch == "\n":
                raise SyntaxAbxError(
                    code="SYN_UNCLOSED_LITERAL",
                    message="Unclosed single-line string literal before newline",
                    location=self._loc(start_line, start_col, len(chars) + 1),
                    hint="Use triple double-quotes for multi-line strings or close quote on same line.",
                )
            if ch == "\\":
                self._advance(1)
                esc = self._advance(1)
                escape_map = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}
                chars.append(escape_map.get(esc, esc))
            else:
                chars.append(self._advance(1))

        raise SyntaxAbxError(
            code="SYN_UNCLOSED_LITERAL",
            message="Unclosed string literal (expected closing double quote)",
            location=self._loc(start_line, start_col, len(chars) + 1),
        )

    def _read_attribute(self) -> Token:
        start_line, start_col = self.line, self.col
        raw = self._advance(1)  # '@'
        while self.pos < self.length and (self._current().isalnum() or self._current() == "_"):
            raw += self._advance(1)

        if len(raw) == 1:
            raise SyntaxAbxError(
                code="SYN_UNEXPECTED_TOKEN",
                message="Empty attribute identifier after '@'",
                location=self._loc(start_line, start_col, 1),
                hint="Specify a valid attribute identifier, e.g. @context, @in, @use.",
            )

        return Token(
            type=TokenType.ATTRIBUTE,
            value=raw,
            raw=raw,
            location=self._loc(start_line, start_col, len(raw)),
        )

    def _read_number(self) -> Token:
        start_line, start_col = self.line, self.col
        raw = ""
        if self._current() == "-":
            raw += self._advance(1)

        has_dot = False
        while self.pos < self.length:
            ch = self._current()
            if ch.isdigit():
                raw += self._advance(1)
            elif ch == "." and not has_dot and self._peek().isdigit():
                has_dot = True
                raw += self._advance(1)
            else:
                break

        value = float(raw) if has_dot else int(raw)
        return Token(
            type=TokenType.NUMBER,
            value=value,
            raw=raw,
            location=self._loc(start_line, start_col, len(raw)),
        )

    def _read_identifier(self) -> Token:
        start_line, start_col = self.line, self.col
        raw = ""
        # Allow alphanumeric, underscore, hyphen, and dot (to preserve file extensions)
        while self.pos < self.length:
            ch = self._current()
            if ch.isalnum() or ch in ("_", "-", "."):
                raw += self._advance(1)
            else:
                break

        if raw == "true":
            return Token(TokenType.BOOLEAN, True, raw, self._loc(start_line, start_col, len(raw)))
        if raw == "false":
            return Token(TokenType.BOOLEAN, False, raw, self._loc(start_line, start_col, len(raw)))

        return Token(
            type=TokenType.IDENTIFIER,
            value=raw,
            raw=raw,
            location=self._loc(start_line, start_col, len(raw)),
        )
