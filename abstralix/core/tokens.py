from dataclasses import dataclass
from enum import Enum, auto
from typing import Any
from abstralix.errors import SourceLocation


class TokenType(Enum):
    # Identifiers and attributes
    IDENTIFIER = auto()     # folder, file, void, main.py, my_func, auto
    ATTRIBUTE = auto()      # @lang, @in, @out, @context, etc.

    # Data literals
    STRING = auto()         # "text" or """multiline"""
    NUMBER = auto()         # 42, 3.14, 0.45
    BOOLEAN = auto()        # true, false

    # Assignment operators
    ASSIGN = auto()         # =
    PLUS_ASSIGN = auto()    # +=
    MINUS_ASSIGN = auto()   # -=

    # Delimiters and punctuation
    LBRACE = auto()         # {
    RBRACE = auto()         # }
    LBRACKET = auto()       # [
    RBRACKET = auto()       # ]
    LPAREN = auto()         # (
    RPAREN = auto()         # )
    COMMA = auto()          # ,

    # End of file
    EOF = auto()


@dataclass
class Token:
    type: TokenType
    value: Any
    raw: str
    location: SourceLocation

    def __repr__(self) -> str:
        return f"Token({self.type.name}, {self.value!r}, line={self.location.line}, col={self.location.column})"
