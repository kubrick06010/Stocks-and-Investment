"""Dependency-inversion contracts for external data and research services."""

from .protocols import (
    FundamentalDataProvider,
    MarketDataProvider,
    ResearchStorageBackend,
    StorageBackend,
    UniverseProvider,
)
from .research_contracts import (
    BacktestDataView,
    PortfolioAnalytics,
    ScoringEngine,
    UniverseSource,
    VersionedStrategy,
)
from .research_intelligence import (
    ChangeDetector, FactorEfficacyAnalyzer, ResearchReportBuilder,
    StrategyComparator, ThesisEngine, WatchlistService,
)
from .statistical_validation import (
    FactorStatisticalValidator,
    MultipleTestingAdjuster,
    ValidationCohortBuilder,
    WalkForwardValidator,
)
from .filings import (
    FilingChangeDetector,
    FilingDocumentProvider,
    FilingEvidenceReader,
    FilingParser,
    QualitativeClaimBuilder,
)
from .automation import AutomationRunReader, AutomationTriggerSource, ResearchAutomationOrchestrator
from .portfolio_construction import PortfolioConstructor
from .interactive import InteractiveResearchService
from .narrative import NarrativeRenderer

__all__ = [
    "FundamentalDataProvider",
    "MarketDataProvider",
    "ResearchStorageBackend",
    "StorageBackend",
    "UniverseProvider",
    "BacktestDataView",
    "PortfolioAnalytics",
    "ScoringEngine",
    "UniverseSource",
    "VersionedStrategy",
    "ChangeDetector",
    "FactorEfficacyAnalyzer",
    "ResearchReportBuilder",
    "StrategyComparator",
    "ThesisEngine",
    "WatchlistService",
    "FactorStatisticalValidator",
    "MultipleTestingAdjuster",
    "ValidationCohortBuilder",
    "WalkForwardValidator",
    "FilingChangeDetector",
    "FilingDocumentProvider",
    "FilingEvidenceReader",
    "FilingParser",
    "QualitativeClaimBuilder",
    "AutomationRunReader",
    "AutomationTriggerSource",
    "ResearchAutomationOrchestrator",
    "PortfolioConstructor",
    "InteractiveResearchService",
    "NarrativeRenderer",
]
