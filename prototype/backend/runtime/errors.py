"""Error codes and exit codes (TRD §6, §7)."""

from __future__ import annotations

# Exit codes of the runner (TRD §6).
EXIT_OK = 0
EXIT_OTHER = 1
EXIT_AUTH = 2
EXIT_PERMISSION = 3
EXIT_WRONG_REQUEST = 4
EXIT_RATE_LIMITED = 5
EXIT_PAGING = 6
EXIT_TIMEOUT = 7
EXIT_HOST_BLOCKED = 8

EXIT_CODES: dict[str, int] = {
    "AUTH_REJECTED": EXIT_AUTH,
    "PERMISSION_OR_SCOPE": EXIT_PERMISSION,
    "PAID_ONLY": EXIT_PERMISSION,
    "WRONG_REQUEST": EXIT_WRONG_REQUEST,
    "MAPPING_FAILED": EXIT_WRONG_REQUEST,
    "RATE_LIMITED_OUT": EXIT_RATE_LIMITED,
    "PAGINATION_LOOP": EXIT_PAGING,
    "CURSOR_EXPIRED": EXIT_PAGING,
    "TIMEOUT": EXIT_TIMEOUT,
    "HOST_BLOCKED": EXIT_HOST_BLOCKED,
    "SERVER_ERROR": EXIT_OTHER,
    "BAD_INPUT": EXIT_OTHER,
}

# A usage-only failure with one of these codes still lets users sync ("partial", TRD §6).
PARTIAL_OK_USAGE_CODES = frozenset({"PERMISSION_OR_SCOPE", "PAID_ONLY"})


class ConnectorError(Exception):
    def __init__(self, code: str, status: int | None = None, detail: str | None = None) -> None:
        super().__init__(code if detail is None else f"{code}: {detail}")
        self.code = code
        self.status = status
        self.detail = detail

    @property
    def exit_code(self) -> int:
        return EXIT_CODES.get(self.code, EXIT_OTHER)
