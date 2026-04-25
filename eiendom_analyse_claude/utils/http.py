from __future__ import annotations

import time
import random
from dataclasses import dataclass, field
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "nb-NO,nb;q=0.9,no;q=0.8,en;q=0.7",
}


@dataclass(frozen=True)
class HttpConfig:
    """Konfigurasjon for HTTP-forespørsler."""
    headers: dict[str, str] | None = None
    timeout_s: float = 15.0
    max_retries: int = 3
    backoff_factor: float = 1.5
    # Tilfeldig pause mellom forespørsler (sekunder)
    min_delay: float = 0.3
    max_delay: float = 1.2

    def resolved_headers(self) -> dict[str, str]:
        merged = dict(DEFAULT_HEADERS)
        if self.headers:
            merged.update(self.headers)
        return merged


def _build_session(cfg: HttpConfig) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=cfg.max_retries,
        backoff_factor=cfg.backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


# Enkel modul-nivå sesjon for gjenbruk
_SESSION: requests.Session | None = None
_SESSION_CFG: HttpConfig | None = None


def get(url: str, cfg: HttpConfig | None = None, delay: bool = True) -> requests.Response:
    """
    GET-forespørsel med retry, automatisk pause og sane defaults.

    Parameters
    ----------
    url : str
    cfg : HttpConfig | None
    delay : bool
        Legg til en liten tilfeldig pause (anbefalt for scraping).
    """
    global _SESSION, _SESSION_CFG
    cfg = cfg or HttpConfig()

    if _SESSION is None or _SESSION_CFG != cfg:
        _SESSION = _build_session(cfg)
        _SESSION_CFG = cfg

    if delay:
        time.sleep(random.uniform(cfg.min_delay, cfg.max_delay))

    resp = _SESSION.get(
        url,
        headers=cfg.resolved_headers(),
        timeout=cfg.timeout_s,
    )
    resp.raise_for_status()
    return resp
