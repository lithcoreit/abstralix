import os
from pathlib import Path
from typing import Any, Dict, List
from abstralix.core.tokens import Token, TokenType
from abstralix.core.ast_nodes import AttributeStmt, ObjectBlock, ProgramAST
from abstralix.errors import SyntaxAbxError, SemanticAbxError
from abstralix.plugins.registry import REGISTRY


class Parser:
    def __init__(self, tokens: List[Token], file_path: str = "<memory>"):
        self.tokens = tokens
        self.file_path = file_path
        self.pos = 0

    def _current(self) -> Token:
        return self.tokens[self.pos]

    def _peek(self, offset: int = 1) -> Token:
        idx = self.pos + offset
        if idx >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[idx]

    def _advance(self) -> Token:
        tok = self.tokens[self.pos]
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
        return tok

    def _expect(self, token_type: TokenType, description: str) -> Token:
        tok = self._current()
        if tok.type != token_type:
            raise SyntaxAbxError(
                code="SYN_UNEXPECTED_TOKEN",
                message=f"Expected {description}, but got '{tok.raw or tok.type.name}'",
                location=tok.location,
            )
        return self._advance()

    def parse(self) -> ProgramAST:
        program = ProgramAST(file_path=self.file_path)
        while self._current().type != TokenType.EOF:
            program.root_objects.append(self._parse_object_block())
        return program

    def _parse_object_block(self) -> ObjectBlock:
        type_tok = self._expect(TokenType.IDENTIFIER, "object type (e.g. 'folder', 'file', 'void')")
        name_tok = self._expect(TokenType.IDENTIFIER, f"name for '{type_tok.value}'")
        self._expect(TokenType.LBRACE, "'{' to open object block")

        block = ObjectBlock(
            obj_type=type_tok.value,
            name=name_tok.value,
            location=type_tok.location,
        )

        while self._current().type not in (TokenType.RBRACE, TokenType.EOF):
            cur = self._current()
            if cur.type == TokenType.ATTRIBUTE:
                block.attributes.append(self._parse_attribute_stmt())
            elif cur.type == TokenType.IDENTIFIER:
                block.children.append(self._parse_object_block())
            else:
                raise SyntaxAbxError(
                    code="SYN_UNEXPECTED_TOKEN",
                    message=f"Unexpected token '{cur.raw}' inside '{block.obj_type} {block.name}'",
                    location=cur.location,
                    hint="Inside an object block, only '@attribute = ...' or child objects are allowed.",
                )

        self._expect(TokenType.RBRACE, f"'}}' to close '{block.obj_type} {block.name}'")
        return block

    def _parse_attribute_stmt(self) -> AttributeStmt:
        attr_tok = self._expect(TokenType.ATTRIBUTE, "attribute name")
        op_tok = self._current()
        if op_tok.type not in (TokenType.ASSIGN, TokenType.PLUS_ASSIGN, TokenType.MINUS_ASSIGN):
            raise SyntaxAbxError(
                code="SYN_INVALID_ASSIGNMENT",
                message=f"Expected assignment operator ('=', '+=', '-=') after '{attr_tok.value}', got '{op_tok.raw}'",
                location=op_tok.location,
            )
        self._advance()
        val = self._parse_value()
        return AttributeStmt(
            name=attr_tok.value,
            operator=op_tok.value,
            value=val,
            location=attr_tok.location,
        )

    def _parse_value(self) -> Any:
        tok = self._current()

        if tok.type == TokenType.STRING:
            self._advance()
            return tok.value

        if tok.type == TokenType.NUMBER:
            self._advance()
            return tok.value

        if tok.type == TokenType.BOOLEAN:
            self._advance()
            return tok.value

        if tok.type == TokenType.LBRACKET:
            return self._parse_list()

        if tok.type == TokenType.LBRACE:
            return self._parse_dict()

        if tok.type == TokenType.IDENTIFIER:
            if self._peek().type == TokenType.LPAREN:
                return self._parse_function_call()
            if tok.value == "auto":
                self._advance()
                return "auto"
            raise SyntaxAbxError(
                code="SYN_UNEXPECTED_TOKEN",
                message=f"Unquoted identifier '{tok.value}' is not a valid value",
                location=tok.location,
                hint=f'Wrap strings in double quotes: "{tok.value}" (only keyword \'auto\' is allowed unquoted).',
            )

        raise SyntaxAbxError(
            code="SYN_UNEXPECTED_TOKEN",
            message=f"Expected a value (string, number, bool, list, dict, or function), got '{tok.raw}'",
            location=tok.location,
        )

    def _parse_list(self) -> List[Any]:
        self._expect(TokenType.LBRACKET, "'['")
        items: List[Any] = []
        while self._current().type not in (TokenType.RBRACKET, TokenType.EOF):
            items.append(self._parse_value())
            if self._current().type == TokenType.COMMA:
                self._advance()
            elif self._current().type != TokenType.RBRACKET:
                raise SyntaxAbxError(
                    code="SYN_UNEXPECTED_TOKEN",
                    message="Expected ',' or ']' in list literal",
                    location=self._current().location,
                )
        self._expect(TokenType.RBRACKET, "']' to close list")
        return items

    def _parse_dict(self) -> Dict[str, Any]:
        self._expect(TokenType.LBRACE, "'{'")
        result: Dict[str, Any] = {}
        while self._current().type not in (TokenType.RBRACE, TokenType.EOF):
            key_tok = self._current()
            if key_tok.type not in (TokenType.IDENTIFIER, TokenType.STRING):
                raise SyntaxAbxError(
                    code="SYN_UNEXPECTED_TOKEN",
                    message=f"Expected dictionary key, got '{key_tok.raw}'",
                    location=key_tok.location,
                )
            self._advance()
            self._expect(TokenType.ASSIGN, "'=' after dictionary key")
            val = self._parse_value()
            result[str(key_tok.value)] = val

            if self._current().type == TokenType.COMMA:
                self._advance()
            elif self._current().type != TokenType.RBRACE:
                raise SyntaxAbxError(
                    code="SYN_UNEXPECTED_TOKEN",
                    message="Expected ',' or '}' in dictionary literal",
                    location=self._current().location,
                )
        self._expect(TokenType.RBRACE, "'}' to close dictionary")
        return result

    def _parse_function_call(self) -> Any:
        fn_tok = self._expect(TokenType.IDENTIFIER, "function name")
        self._expect(TokenType.LPAREN, "'('")
        args: List[Any] = []
        while self._current().type not in (TokenType.RPAREN, TokenType.EOF):
            args.append(self._parse_value())
            if self._current().type == TokenType.COMMA:
                self._advance()
        self._expect(TokenType.RPAREN, "')'")

        fn_name = fn_tok.value
        from abstralix.plugins.registry import REGISTRY
        if fn_name in REGISTRY.functions:
            return REGISTRY.functions[fn_name].execute(args, self.file_path)

        raise SemanticAbxError(
            code="SEM_UNKNOWN_FUNCTION",
            message=f"Unknown compile-time function '{fn_name}()'",
            location=fn_tok.location,
            hint=f"Available function plugins: {', '.join(REGISTRY.functions.keys())}.",
        )