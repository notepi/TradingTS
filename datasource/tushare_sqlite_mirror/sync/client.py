from __future__ import annotations

import os

import pandas as pd
import requests

BASE_URL = "https://tushare.citydata.club"


class CityDataClient:
    """HTTP client for the citydata Tushare proxy."""

    def __init__(self, token: str | None = None, base_url: str = BASE_URL):
        # Tokens are sensitive credentials and must never be written to the mirror database or logs.
        self.token = token or os.getenv("CITYDATA_TOKEN") or os.getenv("TUSHARE_TOKEN")
        self.base_url = base_url.rstrip("/")
        if not self.token:
            raise ValueError("CITYDATA_TOKEN or TUSHARE_TOKEN is required for sync")

    def fetch(self, api_name: str, **kwargs) -> pd.DataFrame:
        payload = {"TOKEN": self.token}
        for key, value in kwargs.items():
            if value not in (None, ""):
                payload[key] = value

        response = requests.post(f"{self.base_url}/{api_name}", data=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        if not data:
            return pd.DataFrame()
        if isinstance(data, dict) and "data" in data:
            raise RuntimeError(str(data["data"]))
        return pd.DataFrame(data)
