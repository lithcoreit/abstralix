from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class BaseLanguagePlugin(ABC):
    language_id: str = "base"

    @abstractmethod
    def build_prompt(
        self,
        void_name: str,
        attributes: Dict[str, Any],
        dependencies_info: List[Dict[str, Any]],
        error_feedback: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        pass

    @abstractmethod
    def check_syntax(self, code: str, void_name: str) -> Tuple[bool, Optional[str]]:
        pass

    @abstractmethod
    def assemble_file(
        self,
        file_attributes: Dict[str, Any],
        voids_code: List[str],
        cross_file_imports: List[Tuple[str, str]],
    ) -> str:
        pass

    @abstractmethod
    async def run_invariant_test(
        self,
        sandbox_root: Path,
        rel_file_path: Path,
        void_name: str,
        invariant_code: str,
    ) -> Tuple[bool, Optional[str]]:
        pass

    @abstractmethod
    def build_auto_invariant_prompt(
        self,
        void_name: str,
        attributes: Dict[str, Any],
    ) -> List[Dict[str, str]]:
        pass