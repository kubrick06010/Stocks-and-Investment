"""Explicit provider registry; no hidden mutable global provider."""

from __future__ import annotations

from typing import TypeVar

from stocks_investment.interfaces.protocols import (
    FundamentalDataProvider,
    MarketDataProvider,
    UniverseProvider,
)

Provider = TypeVar("Provider", MarketDataProvider, FundamentalDataProvider, UniverseProvider)


class ProviderRegistry:
    def __init__(self) -> None:
        self._market: dict[str, MarketDataProvider] = {}
        self._fundamental: dict[str, FundamentalDataProvider] = {}
        self._universe: dict[str, UniverseProvider] = {}

    def register_market_data(self, name: str, provider: MarketDataProvider) -> None:
        self._register(self._market, name, provider)

    def register_fundamentals(self, name: str, provider: FundamentalDataProvider) -> None:
        self._register(self._fundamental, name, provider)

    def register_universe(self, name: str, provider: UniverseProvider) -> None:
        self._register(self._universe, name, provider)

    @staticmethod
    def _register(registry: dict[str, Provider], name: str, provider: Provider) -> None:
        normalized = name.strip().lower()
        if not normalized:
            raise ValueError("provider name must not be empty")
        if normalized in registry:
            raise ValueError(f"provider already registered: {normalized}")
        registry[normalized] = provider

    def market_data(self, name: str) -> MarketDataProvider:
        try:
            return self._market[name.strip().lower()]
        except KeyError as exc:
            raise KeyError(f"market-data provider is not registered: {name}") from exc

    def fundamentals(self, name: str) -> FundamentalDataProvider:
        try:
            return self._fundamental[name.strip().lower()]
        except KeyError as exc:
            raise KeyError(f"fundamental provider is not registered: {name}") from exc

    def universe(self, name: str) -> UniverseProvider:
        try:
            return self._universe[name.strip().lower()]
        except KeyError as exc:
            raise KeyError(f"universe provider is not registered: {name}") from exc

    def names(self) -> dict[str, tuple[str, ...]]:
        return {
            "market": tuple(sorted(self._market)),
            "fundamentals": tuple(sorted(self._fundamental)),
            "universe": tuple(sorted(self._universe)),
        }
