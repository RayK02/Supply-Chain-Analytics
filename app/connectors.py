from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Iterable


class BaseConnector(ABC):
    """Stable boundary: every source yields dictionaries to the import service."""

    @abstractmethod
    def read(self, source: Any, **options: Any) -> Iterable[dict[str, Any]]:
        raise NotImplementedError


class FileImportConnector(BaseConnector):
    extensions: tuple[str, ...] = ()

    def supports(self, path: str | Path) -> bool:
        return Path(path).suffix.lower() in self.extensions


class CSVConnector(FileImportConnector):
    extensions = (".csv", ".tsv")

    def read(self, source: Any, **options: Any) -> Iterable[dict[str, Any]]:
        from .imports import read_csv_rows
        return read_csv_rows(Path(source), options.get("delimiter"))


class ExcelConnector(FileImportConnector):
    extensions = (".xlsx",)

    def read(self, source: Any, **options: Any) -> Iterable[dict[str, Any]]:
        from .imports import read_xlsx_rows
        return read_xlsx_rows(Path(source), options.get("sheet_name"), options.get("header_row", 1))


class BusinessCentralApiConnector(BaseConnector):
    def read(self, source: Any, **options: Any) -> Iterable[dict[str, Any]]:
        raise RuntimeError("BC-API-Connector ist vorbereitet, benötigt aber freigegebene API-Pages und OAuth-Zugangsdaten.")


class NavisionODataConnector(BaseConnector):
    def read(self, source: Any, **options: Any) -> Iterable[dict[str, Any]]:
        raise RuntimeError("NAV-OData-Connector ist vorbereitet, benötigt aber veröffentlichte OData-Services und Authentifizierung.")
