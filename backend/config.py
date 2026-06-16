import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Config:
    host: str = os.getenv("FLASK_HOST", "127.0.0.1")
    port: int = int(os.getenv("FLASK_PORT", "5000"))
    debug: bool = _bool_env("FLASK_DEBUG", True)
    connection_string: str | None = os.getenv("SQLSERVER_CONNECTION_STRING") or None
    driver: str = os.getenv("SQLSERVER_DRIVER", "ODBC Driver 18 for SQL Server")
    server: str = os.getenv("SQLSERVER_SERVER", "localhost")
    database: str = os.getenv("SQLSERVER_DATABASE", "SchoolDB")
    username: str = os.getenv("SQLSERVER_USERNAME", "sa")
    password: str = os.getenv("SQLSERVER_PASSWORD", "")
    trusted_connection: bool = _bool_env("SQLSERVER_TRUSTED_CONNECTION", False)
    trust_certificate: str = os.getenv("SQLSERVER_TRUST_CERTIFICATE", "yes")

    def odbc_connection_string(self) -> str:
        if self.connection_string:
            return self.connection_string

        parts = [
            f"DRIVER={{{self.driver}}}",
            f"SERVER={self.server}",
            f"DATABASE={self.database}",
            f"TrustServerCertificate={self.trust_certificate}",
        ]
        if self.trusted_connection:
            parts.append("Trusted_Connection=yes")
        else:
            parts.extend([f"UID={self.username}", f"PWD={self.password}"])
        return ";".join(parts) + ";"


config = Config()
