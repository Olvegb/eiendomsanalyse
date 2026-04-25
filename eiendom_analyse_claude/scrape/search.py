from __future__ import annotations

import re
from bs4 import BeautifulSoup

from eiendom_analyse_claude.utils.http import get, HttpConfig


FINNKODE_RE = re.compile(r"finnkode=(\d+)")


def search_finn_ads(
    base_search_url: str,
    max_pages: int = 50,
    http_cfg: HttpConfig | None = None,
    verbose: bool = True,
) -> dict[str, str]:
    """
    Crawler FINN søkeresultater og returnerer mapping: finnkode -> absolutt URL.

    Parameters
    ----------
    base_search_url : str
        Søke-URL uten &page= parameter (side 1).
    max_pages : int
        Sikkerhetsgrense for antall sider.
    http_cfg : HttpConfig | None
    verbose : bool
        Print fremgangsinfo.

    Returns
    -------
    dict[str, str]  finnkode -> ad URL
    """
    ads: dict[str, str] = {}
    consecutive_empty = 0

    for page in range(1, max_pages + 1):
        url = base_search_url if page == 1 else f"{base_search_url}&page={page}"

        try:
            resp = get(url, cfg=http_cfg)
        except Exception as e:
            if verbose:
                print(f"[søk] Feil på side {page}: {e}")
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        before = len(ads)

        for a in soup.find_all("a", href=True):
            href = a["href"]
            m = FINNKODE_RE.search(href)
            if not m:
                continue

            finnkode = m.group(1)
            if href.startswith("/"):
                href = "https://www.finn.no" + href

            ads.setdefault(finnkode, href)

        new_ads = len(ads) - before
        if verbose:
            print(f"[søk] Side {page}: +{new_ads} nye annonser (totalt {len(ads)})")

        if new_ads == 0:
            consecutive_empty += 1
            if consecutive_empty >= 2:
                break
        else:
            consecutive_empty = 0

    return ads
