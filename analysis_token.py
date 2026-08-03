from __future__ import annotations

import base64
import json
import zlib
from datetime import date, datetime
from typing import Any

TOKEN_VERSION = 1
MAX_TOKEN_CHARS = 2_500_000
MAX_DECOMPRESSED_BYTES = 20 * 1024 * 1024


class AnalysisTokenError(ValueError):
    pass


def _json_default(value: Any) -> dict[str, str]:
    if isinstance(value, datetime):
        return {"__analysis_type__": "datetime", "value": value.isoformat()}
    if isinstance(value, date):
        return {"__analysis_type__": "date", "value": value.isoformat()}
    raise TypeError(f"Nicht serialisierbarer Wert: {type(value).__name__}")


def _json_object_hook(value: dict[str, Any]) -> Any:
    marker = value.get("__analysis_type__")
    if marker == "date" and set(value) == {"__analysis_type__", "value"}:
        return date.fromisoformat(str(value["value"]))
    if marker == "datetime" and set(value) == {"__analysis_type__", "value"}:
        return datetime.fromisoformat(str(value["value"]))
    return value


def _validate_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("version") != TOKEN_VERSION:
        raise AnalysisTokenError("Der temporäre Analysestatus ist ungültig oder veraltet.")

    expected_types = {
        "results": list,
        "meta": dict,
        "parameters": dict,
        "sales_import": dict,
        "current": dict,
        "current_sources": list,
        "current_filenames": list,
        "source_filename": str,
    }
    for key, expected_type in expected_types.items():
        if not isinstance(payload.get(key), expected_type):
            raise AnalysisTokenError("Der temporäre Analysestatus ist unvollständig.")

    if len(payload["results"]) > 100_000 or len(payload["current"]) > 100_000:
        raise AnalysisTokenError("Der temporäre Analysestatus enthält zu viele Artikel.")
    return payload


def encode_analysis_token(payload: dict[str, Any]) -> str:
    normalized = dict(payload)
    normalized["version"] = TOKEN_VERSION
    raw = json.dumps(
        normalized,
        ensure_ascii=False,
        separators=(",", ":"),
        default=_json_default,
    ).encode("utf-8")
    if len(raw) > MAX_DECOMPRESSED_BYTES:
        raise AnalysisTokenError("Die vorbereitete Analyse ist für die Webversion zu gross.")

    token = base64.urlsafe_b64encode(zlib.compress(raw, level=9)).decode("ascii")
    if len(token) > MAX_TOKEN_CHARS:
        raise AnalysisTokenError("Die vorbereitete Analyse ist für die Webversion zu gross.")
    return token


def decode_analysis_token(token: str) -> dict[str, Any]:
    if not token or len(token) > MAX_TOKEN_CHARS:
        raise AnalysisTokenError("Der temporäre Analysestatus fehlt oder ist zu gross.")
    try:
        compressed = base64.b64decode(token.encode("ascii"), altchars=b"-_", validate=True)
        decompressor = zlib.decompressobj()
        raw = decompressor.decompress(compressed, MAX_DECOMPRESSED_BYTES + 1)
        raw += decompressor.flush()
        if decompressor.unconsumed_tail or len(raw) > MAX_DECOMPRESSED_BYTES:
            raise AnalysisTokenError("Der temporäre Analysestatus ist zu gross.")
        payload = json.loads(raw.decode("utf-8"), object_hook=_json_object_hook)
    except AnalysisTokenError:
        raise
    except (ValueError, TypeError, zlib.error, UnicodeError) as exc:
        raise AnalysisTokenError("Der temporäre Analysestatus ist beschädigt.") from exc
    return _validate_payload(payload)
