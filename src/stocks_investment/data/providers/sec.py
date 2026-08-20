"""SEC EDGAR provider for point-in-time U.S. issuer fundamentals."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from stocks_investment.domain.models import DataProvenance, MetricObservation, MetricStatus, Period, Ticker
from stocks_investment.data.providers._http import ProviderSchemaError, Transport, request_json


class SecEdgarProvider:
    """Normalize SEC company facts into metric observations.

    ``user_agent`` is deliberately required: SEC fair-access policy requires an
    identifying agent with contact information. The injected transport is used by
    deterministic tests and can also be used by applications with a shared client.
    """

    name = "sec-edgar"
    _concepts = {
        "revenue": ("Revenues", "SalesRevenueNet"),
        "net_income": ("ProfitLoss", "NetIncomeLoss"),
        "assets": ("Assets",),
        "liabilities": ("Liabilities",),
        "cash": ("CashAndCashEquivalentsAtCarryingValue",),
        "shares": ("EntityCommonStockSharesOutstanding",),
    }

    def __init__(
        self,
        *,
        user_agent: str,
        timeout: float = 10.0,
        retries: int = 2,
        backoff: float = 0.5,
        transport: Transport | None = None,
        ticker_map: dict[str, str] | None = None,
    ) -> None:
        if not user_agent.strip():
            raise ValueError("SEC user_agent must identify the application and contact")
        if timeout <= 0 or retries < 0 or backoff < 0:
            raise ValueError("timeout must be positive and retries/backoff non-negative")
        self.user_agent = user_agent.strip()
        self.timeout, self.retries, self.backoff = timeout, retries, backoff
        self._transport = transport
        self._ticker_map = {key.upper(): value.zfill(10) for key, value in (ticker_map or {}).items()}
        self._facts_cache: dict[str, dict[str, Any]] = {}

    def metric_inputs(self, ticker: Ticker, period: Period, as_of: date) -> tuple[MetricObservation, ...]:
        cik = self._cik(ticker)
        facts = self._facts(cik)
        observations: list[MetricObservation] = []
        for name, concepts in self._concepts.items():
            fact = self._select_fact(facts, concepts, period, as_of)
            if fact is None:
                continue
            value = fact.get("val")
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                continue
            filed = _parse_date(fact.get("filed"))
            end = _parse_date(fact.get("end"))
            if filed is None or end is None:
                continue
            unit = str(fact.get("unit", ""))
            provenance = DataProvenance(
                source="sec:companyfacts",
                provider=self.name,
                retrieved_at=datetime.now(timezone.utc),
                effective_date=filed,
                available_at=datetime.combine(filed, datetime.min.time(), tzinfo=timezone.utc),
                filing_date=filed,
                period_end=end,
                period=period,
                currency="USD" if unit.startswith("USD") else None,
                units=unit,
                raw_identifier=f"{cik}/{fact.get('accn', '')}/{fact.get('form', '')}/{name}",
            )
            observations.append(MetricObservation(name=name, value=float(value), status=MetricStatus.VALID,
                                                   as_of=filed, provenance=provenance))
        return tuple(observations)

    def _cik(self, ticker: Ticker) -> str:
        if ticker.symbol not in self._ticker_map:
            raise KeyError(f"SEC CIK is not configured for ticker: {ticker.symbol}")
        return self._ticker_map[ticker.symbol]

    def _facts(self, cik: str) -> dict[str, Any]:
        if cik not in self._facts_cache:
            url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
            self._facts_cache[cik] = request_json(url, headers=self._headers(), timeout=self.timeout,
                                                   retries=self.retries, backoff=self.backoff,
                                                   transport=self._transport)
        return self._facts_cache[cik]

    def _headers(self) -> dict[str, str]:
        return {"User-Agent": self.user_agent, "Accept": "application/json"}

    @staticmethod
    def _select_fact(facts: dict[str, Any], concepts: tuple[str, ...], period: Period,
                     as_of: date) -> dict[str, Any] | None:
        taxonomy = facts.get("facts", {}).get("us-gaap", {})
        candidates: list[dict[str, Any]] = []
        for concept in concepts:
            units = taxonomy.get(concept, {}).get("units", {})
            for unit, entries in units.items():
                if not isinstance(entries, list):
                    raise ProviderSchemaError(f"SEC units for {concept} are not a list")
                for entry in entries:
                    if not isinstance(entry, dict) or entry.get("end") != period.end.isoformat():
                        continue
                    filed = _parse_date(entry.get("filed"))
                    if filed is None or filed > as_of:
                        continue
                    start = _parse_date(entry.get("start"))
                    if period.kind.lower() in {"quarter", "quarterly"} and start is not None and (period.end - start).days > 120:
                        continue
                    if period.kind.lower() in {"annual", "year", "fy"} and start is not None and (period.end - start).days < 250:
                        continue
                    candidate = dict(entry)
                    candidate["unit"] = unit
                    candidates.append(candidate)
        return max(candidates, key=lambda item: (str(item.get("filed")), str(item.get("accn", ""))), default=None)


def _parse_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None
