import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


class SecurityUtils:
    """
    Shared security utilities for path and input sanitization.
    """

    # Strict whitelist for symbols: Alphanumeric, underscores, dashes, dots, and colons
    SYMBOL_PATTERN = re.compile(r"^[a-zA-Z0-9_\-.:]+$")

    @staticmethod
    def sanitize_symbol(symbol: str) -> str:
        """
        Validates symbol format and returns a safe string for filenames.
        Replaces colons with underscores.
        Raises ValueError if the symbol contains invalid characters or traversal patterns.
        """
        if not isinstance(symbol, str):
            raise ValueError(f"Symbol must be a string, got {type(symbol)}")

        if not SecurityUtils.SYMBOL_PATTERN.match(symbol):
            raise ValueError(f"Invalid symbol format: {symbol}")

        # Additional protection against traversal even if regex is bypassed or modified
        if ".." in symbol or symbol.startswith("/") or symbol.startswith("\\"):
            raise ValueError(f"Potentially malicious symbol detected: {symbol}")

        # Replace : with _ for file safety
        return symbol.replace(":", "_")

    @staticmethod
    def get_safe_path(base_dir: Path, symbol: str, suffix: str = "_1d.parquet") -> Path:
        """
        Constructs a safe absolute path for a symbol file within base_dir.
        Ensures the path remains within the base directory.
        """
        safe_sym = SecurityUtils.sanitize_symbol(symbol)
        filename = f"{safe_sym}{suffix}"

        # Ensure base_dir is a Path
        base_path = Path(base_dir).resolve()

        # Join and resolve
        target_path = (base_path / filename).resolve()

        # Security check: Ensure the resolved path is still under base_path
        # Using is_relative_to for robust path anchoring
        try:
            if not target_path.is_relative_to(base_path):
                raise ValueError(f"Path traversal attempt detected: {symbol}")
        except AttributeError:
            # Fallback for Python < 3.9 (unlikely given the environment)
            if not str(target_path).startswith(str(base_path)):
                raise ValueError(f"Path traversal attempt detected: {symbol}")

        return target_path

    @staticmethod
    def ensure_safe_path(path: Path | str, allowed_roots: list[Path]) -> Path:
        """
        Enforces strict path anchoring to prevent traversal attacks.

        Args:
            path: The path to validate.
            allowed_roots: List of directories the path is allowed to be in.

        Returns:
            Path: The resolved absolute path.

        Raises:
            ValueError: If the path is outside the allowed roots.
        """
        resolved = Path(path).resolve()
        if not any(resolved.is_relative_to(root.resolve()) for root in allowed_roots):
            raise ValueError(f"Security violation: Path {resolved} is outside allowed roots.")
        return resolved
