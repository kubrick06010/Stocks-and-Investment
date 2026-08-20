"""Alpha Vantage EOD market-data adapter with explicit adjustment semantics."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlencode

from stocks_investment.data.providers._http import ProviderRateLimitError, ProviderSchemaError, Transport, request_json
from stocks_investment.domain.market import (CorporateAction, DividendAction, PriceAdjustmentPolicy, PriceBar,
                                              Quote, SplitAction)
from stocks_investment.domain.models import DataProvenance, Ticker


class AlphaVantageMarketProvider:
    """Normalize documented daily and global-quote responses.

    The API key is accepted at construction or from ``ALPHA_VANTAGE_API_KEY`` by
    the caller; this adapter never stores or logs it. The adjusted daily endpoint
    still supplies raw OHLC, so bars are explicitly marked ``RAW`` and adjustment
    events are returned separately.
    """

    name = "alpha-vantage"

    def __init__(self, *, api_key: str, user_agent: str = "stocks-and-investment/0.1",
                 timeout: float = 10.0, retries: int = 2, backoff: float = 0.5,
                 transport: Transport | None = None) -> None:
        if not api_key.strip():
            raise ValueError("Alpha Vantage api_key must not be empty")
        if timeout <= 0 or retries < 0 or backoff < 0:
            raise ValueError("timeout must be positive and retries/backoff non-negative")
        self._api_key = api_key.strip()
        if not user_agent.strip():
            raise ValueError("Alpha Vantage user_agent must not be empty")
        self.user_agent = user_agent.strip()
        self.timeout, self.retries, self.backoff, self._transport = timeout, retries, backoff, transport

    def prices(self, ticker: Ticker, start: date, end: date) -> tuple[PriceBar, ...]:
        if start > end:
            raise ValueError("start must not be after end")
        payload = self._request("TIME_SERIES_DAILY_ADJUSTED", ticker)
        series = payload.get("Time Series (Daily)")
        if not isinstance(series, dict):
            raise ProviderSchemaError("Alpha Vantage daily response lacks Time Series (Daily)")
        retrieved = datetime.now(timezone.utc)
        bars: list[PriceBar] = []
        for raw_session, raw in series.items():
            session = _parse_date(raw_session)
            if session is None or not start <= session <= end or not isinstance(raw, dict):
                continue
            try:
                open_ = _decimal(raw["1. open"])
                high = _decimal(raw["2. high"])
                low = _decimal(raw["3. low"])
                close = _decimal(raw["4. close"])
                volume = int(raw["6. volume"])
            except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
                raise ProviderSchemaError(f"invalid Alpha Vantage bar for {raw_session}") from exc
            bars.append(PriceBar(ticker=ticker, session=session, open=open_, high=high, low=low,
                                 close=close, volume=volume, currency="USD",
                                 adjustment_policy=PriceAdjustmentPolicy.RAW,
                                 provenance=self._provenance(ticker, session, retrieved, "daily-adjusted")))
        return tuple(sorted(bars, key=lambda bar: bar.session))

    def quote(self, ticker: Ticker, as_of: date) -> Quote | None:
        payload = self._request("GLOBAL_QUOTE", ticker)
        raw = payload.get("Global Quote")
        if not isinstance(raw, dict) or not raw.get("05. price") or not raw.get("07. latest trading day"):
            return None
        observed = _parse_date(raw["07. latest trading day"])
        if observed is None or observed > as_of:
            return None
        retrieved = datetime.now(timezone.utc)
        return Quote(ticker=ticker, price=_decimal(raw["05. price"]),
                     observed_at=datetime.combine(observed, datetime.min.time(), tzinfo=timezone.utc),
                     currency="USD", provenance=self._provenance(ticker, observed, retrieved, "global-quote"))

    def corporate_actions(self, ticker: Ticker, start: date, end: date) -> tuple[CorporateAction, ...]:
        if start > end:
            raise ValueError("start must not be after end")
        payload = self._request("TIME_SERIES_DAILY_ADJUSTED", ticker)
        series = payload.get("Time Series (Daily)")
        if not isinstance(series, dict):
            raise ProviderSchemaError("Alpha Vantage daily response lacks Time Series (Daily)")
        retrieved = datetime.now(timezone.utc)
        actions: list[CorporateAction] = []
        for raw_session, raw in series.items():
            session = _parse_date(raw_session)
            if session is None or not start <= session <= end or not isinstance(raw, dict):
                continue
            provenance = self._provenance(ticker, session, retrieved, "daily-adjusted")
            dividend = _decimal(raw.get("7. dividend amount", "0"))
            if dividend > 0:
                actions.append(DividendAction(ticker=ticker, ex_date=session, amount_per_share=dividend,
                                              currency="USD", provenance=provenance))
            coefficient = _decimal(raw.get("8. split coefficient", "1"))
            if coefficient != 1:
                numerator, denominator = coefficient.as_integer_ratio()
                actions.append(SplitAction(ticker=ticker, ex_date=session, numerator=numerator,
                                           denominator=denominator, provenance=provenance))
        return tuple(sorted(actions, key=lambda action: action.ex_date))

    def provenance(self, ticker: Ticker, as_of: date) -> tuple[DataProvenance, ...]:
        return tuple(bar.provenance for bar in self.prices(ticker, as_of, as_of))

    def _request(self, function: str, ticker: Ticker) -> dict[str, Any]:
        query = urlencode({"function": function, "symbol": ticker.symbol, "apikey": self._api_key, "outputsize": "full"})
        payload = request_json(f"https://www.alphavantage.co/query?{query}",
                               headers={"Accept": "application/json", "User-Agent": self.user_agent},
                               timeout=self.timeout, retries=self.retries, backoff=self.backoff, transport=self._transport)
        if "Note" in payload or "Information" in payload:
            raise ProviderRateLimitError(str(payload.get("Note") or payload.get("Information")))
        if "Error Message" in payload:
            raise ProviderSchemaError(str(payload["Error Message"]))
        return payload

    def _provenance(self, ticker: Ticker, session: date, retrieved: datetime, endpoint: str) -> DataProvenance:
        return DataProvenance(source=f"alpha-vantage:{endpoint}", provider=self.name, retrieved_at=retrieved,
                              effective_date=session, available_at=retrieved, currency="USD",
                              units="USD/share", raw_identifier=f"{ticker.symbol}/{session.isoformat()}")


def _decimal(value: object) -> Decimal:
    return Decimal(str(value))


def _parse_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None
