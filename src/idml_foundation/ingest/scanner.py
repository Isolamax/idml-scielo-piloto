import socket
from dataclasses import dataclass
from typing import Protocol

from idml_foundation.settings import Settings


@dataclass(frozen=True)
class ScanResult:
    clean: bool
    status: str


class ScannerUnavailableError(RuntimeError):
    pass


class ContentScanner(Protocol):
    def scan(self, data: bytes) -> ScanResult: ...


class PolicyOnlyScanner:
    def scan(self, data: bytes) -> ScanResult:
        del data
        return ScanResult(clean=True, status="policy_only")


class ClamAVScanner:
    def __init__(self, host: str, port: int, timeout: float = 30.0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout

    def scan(self, data: bytes) -> ScanResult:
        try:
            with socket.create_connection(
                (self.host, self.port), timeout=self.timeout
            ) as connection:
                connection.sendall(b"zINSTREAM\0")
                view = memoryview(data)
                for offset in range(0, len(view), 64 * 1024):
                    chunk = view[offset : offset + 64 * 1024]
                    connection.sendall(len(chunk).to_bytes(4, "big"))
                    connection.sendall(chunk)
                connection.sendall((0).to_bytes(4, "big"))
                response = connection.recv(4096).decode("utf-8", errors="replace")
        except OSError as exc:
            raise ScannerUnavailableError("content scanner unavailable") from exc
        if response.endswith("OK\0") or response.rstrip("\0\n").endswith("OK"):
            return ScanResult(clean=True, status="clamav_clean")
        if "FOUND" in response:
            return ScanResult(clean=False, status="malware_detected")
        raise ScannerUnavailableError("content scanner returned an indeterminate response")


def build_scanner(settings: Settings) -> ContentScanner:
    if settings.feature_clamav:
        return ClamAVScanner(settings.clamav_host, settings.clamav_port)
    return PolicyOnlyScanner()
