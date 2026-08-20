"""Small SQLite persistence layer for normalized observations and raw payloads."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

from stocks_investment.domain.models import (
    DataProvenance,
    MetricObservation,
    MetricStatus,
    Period,
    Ticker,
)
from stocks_investment.domain.filings import (
    ClaimCategory,
    ClaimDirection,
    ClaimMethod,
    ClaimStatus,
    FilingChangeType,
    FilingDocument,
    FilingEvidenceReference,
    FilingEvidenceSnapshot,
    FilingForm,
    FilingSection,
    FilingSectionChange,
    FilingSectionKind,
    QualitativeClaim,
)
from stocks_investment.domain.research import ResearchResult, ResearchRun, ResearchRunStatus
from stocks_investment.domain.research_engine import (
    AnalysisStatus, CriterionResult, CriterionStatus, FactorObservation, FactorScore,
    ResearchOutcome, UniverseLimitation, UniverseSnapshot,
)
from stocks_investment.domain.research_intelligence import (
    ChangeType, CohortIdentity, DriverDirection, FactorOutcomeObservation, MonitoringEvent, ResearchChangeEvent,
    SourceReference, ThesisAssumption, ThesisClassification, ThesisDriver, ThesisDriverCategory,
    ThesisInvalidator, ThesisSnapshot, WatchCondition, WatchlistEntry, WatchlistStatus,
)
from stocks_investment.domain.statistical_validation import (
    BootstrapMethod,
    ConfidenceInterval,
    CrossSectionalICObservation,
    DataPartition,
    DateWindow,
    FactorValidationSummary,
    SamplingMethod,
    StatisticalDatasetManifest,
    StatisticalStatus,
    StatisticalValidationRun,
    ValidationCohort,
)
from stocks_investment.backtesting.engine import (
    BacktestConfigV1, BacktestPeriod, BacktestRun, CorporateActionMode, SecurityAttribution,
)
from stocks_investment.domain.automation import (
    AutomationFailureKind,
    AutomationRun,
    AutomationRunStatus,
    AutomationStepName,
    AutomationStepResult,
    AutomationStepStatus,
    AutomationTrigger,
    AutomationTriggerKind,
    ResearchAutomationDefinition,
    RetryPolicy,
)
from stocks_investment.domain.portfolio_construction import (
    ConstraintEvaluation,
    ConstraintStatus,
    ConstructionStatus,
    CurrentPortfolioWeight,
    PortfolioConstraint,
    PortfolioConstraintKind,
    PortfolioConstructionPolicy,
    PortfolioConstructionRequest,
    PortfolioConstructionResult,
    TargetPosition,
    TradeEstimate,
    WeightingMethod,
)


class SQLiteStorage:
    """A deterministic local store with an explicit schema version."""

    schema_version = 10

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path)
        self._connection.row_factory = sqlite3.Row
        self._migrate()

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "SQLiteStorage":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _migrate(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS raw_payloads (
                content_hash TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                parameters_json TEXT NOT NULL,
                payload TEXT NOT NULL,
                retrieved_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS metric_observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                name TEXT NOT NULL,
                value REAL,
                status TEXT NOT NULL,
                as_of TEXT NOT NULL,
                provenance_json TEXT NOT NULL,
                source_inputs_json TEXT NOT NULL,
                explanation TEXT,
                UNIQUE(ticker, name, as_of, provenance_json)
            );
            CREATE TABLE IF NOT EXISTS research_runs (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                as_of TEXT NOT NULL,
                strategy_name TEXT NOT NULL,
                strategy_version TEXT NOT NULL,
                universe_name TEXT NOT NULL,
                universe_version TEXT,
                universe_as_of TEXT,
                parameters_json TEXT NOT NULL,
                git_commit TEXT,
                data_snapshot TEXT,
                status TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS research_results (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL REFERENCES research_runs(id),
                ticker TEXT NOT NULL,
                created_at TEXT NOT NULL,
                rank INTEGER,
                composite_score REAL,
                classification TEXT,
                factor_scores_json TEXT NOT NULL DEFAULT '[]',
                criteria_json TEXT NOT NULL DEFAULT '[]'
            );
            CREATE TABLE IF NOT EXISTS universe_snapshots (
                name TEXT NOT NULL,
                version TEXT NOT NULL,
                as_of TEXT NOT NULL,
                members_json TEXT NOT NULL,
                source TEXT NOT NULL,
                provenance_json TEXT NOT NULL,
                limitations_json TEXT NOT NULL,
                PRIMARY KEY(name, version)
            );
            CREATE TABLE IF NOT EXISTS research_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                result_id TEXT NOT NULL REFERENCES research_results(id),
                measured_at TEXT NOT NULL,
                horizon TEXT NOT NULL,
                forward_return REAL,
                benchmark_return REAL,
                excess_return REAL,
                UNIQUE(result_id, horizon)
            );
            CREATE TABLE IF NOT EXISTS backtest_runs (
                id TEXT PRIMARY KEY,
                strategy_name TEXT NOT NULL,
                strategy_version TEXT NOT NULL,
                config_json TEXT NOT NULL,
                final_value REAL NOT NULL,
                status TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS backtest_periods (
                backtest_run_id TEXT NOT NULL REFERENCES backtest_runs(id),
                period_index INTEGER NOT NULL,
                research_run_id TEXT NOT NULL,
                rebalance_date TEXT NOT NULL,
                holding_start TEXT NOT NULL,
                holding_end TEXT NOT NULL,
                starting_value REAL NOT NULL,
                ending_value REAL NOT NULL,
                gross_return REAL NOT NULL,
                turnover REAL NOT NULL,
                transaction_cost REAL NOT NULL,
                net_return REAL NOT NULL,
                benchmark_return REAL,
                excess_return REAL,
                selected_symbols_json TEXT NOT NULL,
                attribution_json TEXT NOT NULL,
                PRIMARY KEY(backtest_run_id, period_index)
            );
            CREATE TABLE IF NOT EXISTS thesis_snapshots (
                id TEXT PRIMARY KEY,
                ticker TEXT NOT NULL,
                research_run_id TEXT NOT NULL,
                research_result_id TEXT NOT NULL,
                as_of TEXT NOT NULL,
                thesis_version TEXT NOT NULL,
                classification TEXT NOT NULL,
                summary TEXT NOT NULL,
                drivers_json TEXT NOT NULL,
                assumptions_json TEXT NOT NULL,
                invalidators_json TEXT NOT NULL,
                structured_views_json TEXT NOT NULL,
                confidence REAL,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS research_change_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                from_run_id TEXT NOT NULL,
                to_run_id TEXT NOT NULL,
                from_as_of TEXT NOT NULL,
                to_as_of TEXT NOT NULL,
                change_type TEXT NOT NULL,
                field TEXT NOT NULL,
                old_value_json TEXT NOT NULL,
                new_value_json TEXT NOT NULL,
                magnitude REAL,
                materiality TEXT NOT NULL,
                source_references_json TEXT NOT NULL,
                UNIQUE(ticker, from_run_id, to_run_id, change_type, field)
            );
            CREATE TABLE IF NOT EXISTS watchlist_entries (
                id TEXT PRIMARY KEY,
                ticker TEXT NOT NULL,
                created_at TEXT NOT NULL,
                source_run_id TEXT NOT NULL,
                source_result_id TEXT NOT NULL,
                reason TEXT NOT NULL,
                status TEXT NOT NULL,
                priority INTEGER NOT NULL,
                tags_json TEXT NOT NULL,
                conditions_json TEXT NOT NULL,
                notes TEXT
            );
            CREATE TABLE IF NOT EXISTS monitoring_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                watchlist_entry_id TEXT NOT NULL,
                research_run_id TEXT NOT NULL,
                as_of TEXT NOT NULL,
                condition_json TEXT NOT NULL,
                previous_state_json TEXT NOT NULL,
                current_state_json TEXT NOT NULL,
                triggered INTEGER NOT NULL,
                rationale TEXT NOT NULL,
                UNIQUE(watchlist_entry_id, research_run_id, as_of)
            );
            CREATE TABLE IF NOT EXISTS factor_outcome_observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                factor_name TEXT NOT NULL,
                factor_version TEXT NOT NULL,
                research_run_id TEXT NOT NULL,
                ticker TEXT NOT NULL,
                as_of TEXT NOT NULL,
                factor_score REAL,
                horizon TEXT NOT NULL,
                security_return REAL,
                benchmark_return REAL,
                excess_return REAL,
                outcome_status TEXT NOT NULL,
                universe TEXT NOT NULL,
                benchmark TEXT NOT NULL,
                base_currency TEXT NOT NULL,
                rebalance_cadence TEXT NOT NULL,
                UNIQUE(research_run_id, ticker, factor_name, factor_version, horizon,
                       universe, benchmark, base_currency, rebalance_cadence)
            );
            CREATE TABLE IF NOT EXISTS statistical_dataset_manifests (
                id TEXT PRIMARY KEY,
                version TEXT NOT NULL,
                created_at TEXT NOT NULL,
                window_start TEXT NOT NULL,
                window_end TEXT NOT NULL,
                base_currency TEXT NOT NULL,
                factor_versions_json TEXT NOT NULL,
                universe_versions_json TEXT NOT NULL,
                benchmarks_json TEXT NOT NULL,
                source_snapshot_ids_json TEXT NOT NULL,
                limitations_json TEXT NOT NULL,
                metadata_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS validation_cohorts (
                id TEXT PRIMARY KEY,
                dataset_manifest_id TEXT NOT NULL REFERENCES statistical_dataset_manifests(id),
                identity_json TEXT NOT NULL,
                partition TEXT NOT NULL,
                sampling_method TEXT NOT NULL,
                observation_ids_json TEXT NOT NULL,
                overlapping_horizons INTEGER NOT NULL,
                minimum_sample_size INTEGER NOT NULL,
                minimum_coverage REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS statistical_validation_runs (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                methodology_version TEXT NOT NULL,
                dataset_manifest_id TEXT NOT NULL REFERENCES statistical_dataset_manifests(id),
                cohort_ids_json TEXT NOT NULL,
                parameters_json TEXT NOT NULL,
                status TEXT NOT NULL,
                git_commit TEXT
            );
            CREATE TABLE IF NOT EXISTS factor_validation_summaries (
                validation_run_id TEXT NOT NULL REFERENCES statistical_validation_runs(id),
                factor_name TEXT NOT NULL,
                factor_version TEXT NOT NULL,
                cohort_id TEXT NOT NULL REFERENCES validation_cohorts(id),
                methodology_version TEXT NOT NULL,
                status TEXT NOT NULL,
                eligible_observations INTEGER NOT NULL,
                usable_observations INTEGER NOT NULL,
                coverage REAL NOT NULL,
                cross_sectional_ic_json TEXT NOT NULL,
                rank_ic_confidence_interval_json TEXT,
                turnover_adjusted_spread REAL,
                metadata_json TEXT NOT NULL,
                PRIMARY KEY(validation_run_id, factor_name, factor_version, cohort_id)
            );
            CREATE TABLE IF NOT EXISTS filing_documents (
                id TEXT PRIMARY KEY,
                ticker TEXT NOT NULL,
                cik TEXT NOT NULL,
                accession_number TEXT NOT NULL,
                form TEXT NOT NULL,
                filed_at TEXT NOT NULL,
                available_at TEXT NOT NULL,
                period_end TEXT,
                primary_document TEXT NOT NULL,
                source_url TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                retrieved_at TEXT NOT NULL,
                mime_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                provenance_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS filing_sections (
                id TEXT PRIMARY KEY,
                filing_id TEXT NOT NULL REFERENCES filing_documents(id),
                item TEXT NOT NULL,
                title TEXT NOT NULL,
                kind TEXT NOT NULL,
                ordinal INTEGER NOT NULL,
                normalized_text TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                source_start INTEGER NOT NULL,
                source_end INTEGER NOT NULL,
                parser_version TEXT NOT NULL,
                metadata_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS qualitative_claims (
                id TEXT PRIMARY KEY,
                ticker TEXT NOT NULL,
                as_of TEXT NOT NULL,
                filing_id TEXT NOT NULL REFERENCES filing_documents(id),
                methodology_version TEXT NOT NULL,
                category TEXT NOT NULL,
                direction TEXT NOT NULL,
                statement TEXT NOT NULL,
                status TEXT NOT NULL,
                method TEXT NOT NULL,
                source_references_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                metadata_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS filing_section_changes (
                id TEXT PRIMARY KEY,
                ticker TEXT NOT NULL,
                from_filing_id TEXT NOT NULL REFERENCES filing_documents(id),
                to_filing_id TEXT NOT NULL REFERENCES filing_documents(id),
                from_section_id TEXT,
                to_section_id TEXT,
                change_type TEXT NOT NULL,
                methodology_version TEXT NOT NULL,
                similarity REAL,
                material INTEGER NOT NULL,
                rationale TEXT NOT NULL,
                source_references_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS filing_evidence_snapshots (
                id TEXT PRIMARY KEY,
                ticker TEXT NOT NULL,
                as_of TEXT NOT NULL,
                filing_ids_json TEXT NOT NULL,
                section_ids_json TEXT NOT NULL,
                claim_ids_json TEXT NOT NULL,
                methodology_version TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS automation_definitions (
                identity TEXT PRIMARY KEY,
                definition_id TEXT NOT NULL,
                version TEXT NOT NULL,
                pipeline_version TEXT NOT NULL,
                trigger_kinds_json TEXT NOT NULL,
                strategy_name TEXT NOT NULL,
                strategy_version TEXT NOT NULL,
                universe_name TEXT NOT NULL,
                schedule TEXT,
                retry_policy_json TEXT NOT NULL,
                enabled INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                parameters_json TEXT NOT NULL,
                UNIQUE(definition_id, version)
            );
            CREATE TABLE IF NOT EXISTS automation_triggers (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                as_of TEXT NOT NULL,
                deduplication_key TEXT NOT NULL UNIQUE,
                source_references_json TEXT NOT NULL,
                tickers_json TEXT NOT NULL,
                metadata_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS automation_runs (
                id TEXT PRIMARY KEY,
                definition_id TEXT NOT NULL,
                definition_version TEXT NOT NULL,
                pipeline_version TEXT NOT NULL,
                trigger_id TEXT NOT NULL REFERENCES automation_triggers(id),
                idempotency_key TEXT NOT NULL UNIQUE,
                as_of TEXT NOT NULL,
                status TEXT NOT NULL,
                attempt INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                steps_json TEXT NOT NULL,
                source_references_json TEXT NOT NULL,
                output_references_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS portfolio_construction_policies (
                identity TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                version TEXT NOT NULL,
                weighting_method TEXT NOT NULL,
                constraints_json TEXT NOT NULL,
                transaction_cost_model TEXT NOT NULL,
                transaction_cost_rate REAL NOT NULL,
                allow_fractional_shares INTEGER NOT NULL,
                parameters_json TEXT NOT NULL,
                UNIQUE(name, version)
            );
            CREATE TABLE IF NOT EXISTS portfolio_construction_requests (
                id TEXT PRIMARY KEY,
                as_of TEXT NOT NULL,
                research_run_id TEXT NOT NULL,
                research_result_ids_json TEXT NOT NULL,
                policy_name TEXT NOT NULL,
                policy_version TEXT NOT NULL,
                capital REAL NOT NULL,
                base_currency TEXT NOT NULL,
                current_weights_json TEXT NOT NULL,
                source_references_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS portfolio_construction_results (
                id TEXT PRIMARY KEY,
                request_id TEXT NOT NULL REFERENCES portfolio_construction_requests(id),
                methodology_version TEXT NOT NULL,
                status TEXT NOT NULL,
                targets_json TEXT NOT NULL,
                cash_weight REAL NOT NULL,
                gross_traded_notional REAL NOT NULL,
                turnover REAL NOT NULL,
                estimated_transaction_cost REAL NOT NULL,
                trades_json TEXT NOT NULL,
                constraints_json TEXT NOT NULL,
                source_references_json TEXT NOT NULL,
                notes_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS research_result_observations (
                result_id TEXT NOT NULL REFERENCES research_results(id),
                observation_id INTEGER NOT NULL REFERENCES metric_observations(id),
                PRIMARY KEY (result_id, observation_id)
            );
            """
        )
        self._ensure_column("research_runs", "universe_version", "TEXT")
        self._ensure_column("research_runs", "universe_as_of", "TEXT")
        self._ensure_column("research_results", "factor_scores_json", "TEXT NOT NULL DEFAULT '[]'")
        self._ensure_column("research_results", "criteria_json", "TEXT NOT NULL DEFAULT '[]'")
        self._connection.execute(
            "INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('version', ?)",
            (str(self.schema_version),),
        )
        self._connection.commit()

    def save_statistical_dataset_manifest(self, manifest: StatisticalDatasetManifest) -> None:
        self._connection.execute(
            """INSERT OR REPLACE INTO statistical_dataset_manifests
               (id, version, created_at, window_start, window_end, base_currency,
                factor_versions_json, universe_versions_json, benchmarks_json,
                source_snapshot_ids_json, limitations_json, metadata_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                manifest.id,
                manifest.version,
                manifest.created_at.isoformat(),
                manifest.window.start.isoformat(),
                manifest.window.end.isoformat(),
                manifest.base_currency,
                json.dumps(manifest.factor_versions),
                json.dumps(manifest.universe_versions),
                json.dumps(manifest.benchmarks),
                json.dumps(manifest.source_snapshot_ids),
                json.dumps(manifest.limitations),
                json.dumps(dict(manifest.metadata), sort_keys=True),
            ),
        )
        self._connection.commit()

    def load_statistical_dataset_manifest(self, manifest_id: str) -> StatisticalDatasetManifest | None:
        row = self._connection.execute(
            "SELECT * FROM statistical_dataset_manifests WHERE id = ?", (manifest_id,)
        ).fetchone()
        if row is None:
            return None
        return StatisticalDatasetManifest(
            id=row["id"],
            version=row["version"],
            created_at=datetime.fromisoformat(row["created_at"]),
            window=DateWindow(date.fromisoformat(row["window_start"]), date.fromisoformat(row["window_end"])),
            base_currency=row["base_currency"],
            factor_versions=tuple(json.loads(row["factor_versions_json"])),
            universe_versions=tuple(json.loads(row["universe_versions_json"])),
            benchmarks=tuple(json.loads(row["benchmarks_json"])),
            source_snapshot_ids=tuple(json.loads(row["source_snapshot_ids_json"])),
            limitations=tuple(json.loads(row["limitations_json"])),
            metadata=json.loads(row["metadata_json"]),
        )

    def save_validation_cohort(self, cohort: ValidationCohort) -> None:
        identity = cohort.identity
        identity_json = json.dumps(
            {
                "factor_version": identity.factor_version,
                "universe": identity.universe,
                "date_start": identity.date_start.isoformat(),
                "date_end": identity.date_end.isoformat(),
                "outcome_horizon": identity.outcome_horizon,
                "rebalance_cadence": identity.rebalance_cadence,
                "base_currency": identity.base_currency,
                "benchmark": identity.benchmark,
            },
            sort_keys=True,
        )
        self._connection.execute(
            """INSERT OR REPLACE INTO validation_cohorts
               (id, dataset_manifest_id, identity_json, partition, sampling_method,
                observation_ids_json, overlapping_horizons, minimum_sample_size, minimum_coverage)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                cohort.id,
                cohort.dataset_manifest_id,
                identity_json,
                cohort.partition.value,
                cohort.sampling_method.value,
                json.dumps(cohort.observation_ids),
                int(cohort.overlapping_horizons),
                cohort.minimum_sample_size,
                cohort.minimum_coverage,
            ),
        )
        self._connection.commit()

    def load_validation_cohort(self, cohort_id: str) -> ValidationCohort | None:
        row = self._connection.execute(
            "SELECT * FROM validation_cohorts WHERE id = ?", (cohort_id,)
        ).fetchone()
        if row is None:
            return None
        identity = json.loads(row["identity_json"])
        return ValidationCohort(
            id=row["id"],
            dataset_manifest_id=row["dataset_manifest_id"],
            identity=CohortIdentity(
                identity["factor_version"],
                identity["universe"],
                date.fromisoformat(identity["date_start"]),
                date.fromisoformat(identity["date_end"]),
                identity["outcome_horizon"],
                identity["rebalance_cadence"],
                identity["base_currency"],
                identity["benchmark"],
            ),
            partition=DataPartition(row["partition"]),
            sampling_method=SamplingMethod(row["sampling_method"]),
            observation_ids=tuple(json.loads(row["observation_ids_json"])),
            overlapping_horizons=bool(row["overlapping_horizons"]),
            minimum_sample_size=int(row["minimum_sample_size"]),
            minimum_coverage=float(row["minimum_coverage"]),
        )

    def save_statistical_validation_run(self, run: StatisticalValidationRun) -> None:
        self._connection.execute(
            """INSERT OR REPLACE INTO statistical_validation_runs
               (id, created_at, methodology_version, dataset_manifest_id, cohort_ids_json,
                parameters_json, status, git_commit)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run.id,
                run.created_at.isoformat(),
                run.methodology_version,
                run.dataset_manifest_id,
                json.dumps(run.cohort_ids),
                json.dumps(dict(run.parameters), sort_keys=True),
                run.status.value,
                run.git_commit,
            ),
        )
        self._connection.commit()

    def load_statistical_validation_run(self, run_id: str) -> StatisticalValidationRun | None:
        row = self._connection.execute(
            "SELECT * FROM statistical_validation_runs WHERE id = ?", (run_id,)
        ).fetchone()
        if row is None:
            return None
        return StatisticalValidationRun(
            id=row["id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            methodology_version=row["methodology_version"],
            dataset_manifest_id=row["dataset_manifest_id"],
            cohort_ids=tuple(json.loads(row["cohort_ids_json"])),
            parameters=json.loads(row["parameters_json"]),
            status=StatisticalStatus(row["status"]),
            git_commit=row["git_commit"],
        )

    def save_factor_validation_summary(
        self, validation_run_id: str, summary: FactorValidationSummary
    ) -> None:
        cross_sectional_ic = [
            {
                "as_of": item.as_of.isoformat(),
                "factor_name": item.factor_name,
                "factor_version": item.factor_version,
                "outcome_horizon": item.outcome_horizon,
                "universe": item.universe,
                "benchmark": item.benchmark,
                "sample_size": item.sample_size,
                "rank_ic": item.rank_ic,
                "status": item.status.value,
            }
            for item in summary.cross_sectional_ic
        ]
        interval = summary.rank_ic_confidence_interval
        interval_json = None if interval is None else json.dumps(
            {
                "estimate": interval.estimate,
                "lower": interval.lower,
                "upper": interval.upper,
                "confidence_level": interval.confidence_level,
                "method": interval.method.value,
                "resamples": interval.resamples,
                "block_size": interval.block_size,
            },
            sort_keys=True,
        )
        self._connection.execute(
            """INSERT OR REPLACE INTO factor_validation_summaries
               (validation_run_id, factor_name, factor_version, cohort_id, methodology_version,
                status, eligible_observations, usable_observations, coverage,
                cross_sectional_ic_json, rank_ic_confidence_interval_json,
                turnover_adjusted_spread, metadata_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                validation_run_id,
                summary.factor_name,
                summary.factor_version,
                summary.cohort_id,
                summary.methodology_version,
                summary.status.value,
                summary.eligible_observations,
                summary.usable_observations,
                summary.coverage,
                json.dumps(cross_sectional_ic, sort_keys=True),
                interval_json,
                summary.turnover_adjusted_spread,
                json.dumps(dict(summary.metadata), sort_keys=True),
            ),
        )
        self._connection.commit()

    def load_factor_validation_summaries(
        self, validation_run_id: str
    ) -> tuple[FactorValidationSummary, ...]:
        rows = self._connection.execute(
            """SELECT * FROM factor_validation_summaries
               WHERE validation_run_id = ? ORDER BY factor_name, factor_version, cohort_id""",
            (validation_run_id,),
        ).fetchall()
        summaries: list[FactorValidationSummary] = []
        for row in rows:
            ic_items = tuple(
                CrossSectionalICObservation(
                    date.fromisoformat(item["as_of"]),
                    item["factor_name"],
                    item["factor_version"],
                    item["outcome_horizon"],
                    item["universe"],
                    item["benchmark"],
                    item["sample_size"],
                    item["rank_ic"],
                    StatisticalStatus(item["status"]),
                )
                for item in json.loads(row["cross_sectional_ic_json"])
            )
            interval_value = row["rank_ic_confidence_interval_json"]
            interval = None
            if interval_value is not None:
                item = json.loads(interval_value)
                interval = ConfidenceInterval(
                    item["estimate"],
                    item["lower"],
                    item["upper"],
                    item["confidence_level"],
                    BootstrapMethod(item["method"]),
                    item["resamples"],
                    item["block_size"],
                )
            summaries.append(
                FactorValidationSummary(
                    row["factor_name"],
                    row["factor_version"],
                    row["cohort_id"],
                    row["methodology_version"],
                    StatisticalStatus(row["status"]),
                    row["eligible_observations"],
                    row["usable_observations"],
                    row["coverage"],
                    ic_items,
                    interval,
                    row["turnover_adjusted_spread"],
                    json.loads(row["metadata_json"]),
                )
            )
        return tuple(summaries)

    def save_filing_document(self, filing: FilingDocument) -> None:
        self._save_immutable(
            "filing_documents",
            "id",
            (
                "id", "ticker", "cik", "accession_number", "form", "filed_at",
                "available_at", "period_end", "primary_document", "source_url",
                "content_hash", "retrieved_at", "mime_type", "size_bytes", "provenance_json",
            ),
            (
                filing.id, filing.ticker.symbol, filing.cik, filing.accession_number,
                filing.form.value, filing.filed_at.isoformat(), filing.available_at.isoformat(),
                filing.period_end.isoformat() if filing.period_end else None,
                filing.primary_document, filing.source_url, filing.content_hash,
                filing.retrieved_at.isoformat(), filing.mime_type, filing.size_bytes,
                json.dumps(_provenance_to_dict(filing.provenance), sort_keys=True),
            ),
        )

    def load_filing_document(self, filing_id: str) -> FilingDocument | None:
        row = self._connection.execute(
            "SELECT * FROM filing_documents WHERE id = ?", (filing_id,)
        ).fetchone()
        if row is None:
            return None
        return _filing_document_from_row(row)

    def load_filings_available_on(self, ticker: Ticker, as_of: date) -> tuple[FilingDocument, ...]:
        rows = self._connection.execute(
            """SELECT * FROM filing_documents
               WHERE ticker = ? AND substr(available_at, 1, 10) <= ?
               ORDER BY available_at, accession_number, id""",
            (ticker.symbol, as_of.isoformat()),
        ).fetchall()
        return tuple(_filing_document_from_row(row) for row in rows)

    def save_filing_section(self, section: FilingSection) -> None:
        self._save_immutable(
            "filing_sections",
            "id",
            (
                "id", "filing_id", "item", "title", "kind", "ordinal",
                "normalized_text", "content_hash", "source_start", "source_end",
                "parser_version", "metadata_json",
            ),
            (
                section.id, section.filing_id, section.item, section.title, section.kind.value,
                section.ordinal, section.normalized_text, section.content_hash,
                section.source_start, section.source_end, section.parser_version,
                json.dumps(dict(section.metadata), sort_keys=True),
            ),
        )

    def load_filing_sections(self, filing_id: str) -> tuple[FilingSection, ...]:
        rows = self._connection.execute(
            "SELECT * FROM filing_sections WHERE filing_id = ? ORDER BY ordinal, id", (filing_id,)
        ).fetchall()
        return tuple(_filing_section_from_row(row) for row in rows)

    def save_qualitative_claim(self, claim: QualitativeClaim) -> None:
        self._save_immutable(
            "qualitative_claims",
            "id",
            (
                "id", "ticker", "as_of", "filing_id", "methodology_version", "category",
                "direction", "statement", "status", "method", "source_references_json",
                "created_at", "metadata_json",
            ),
            (
                claim.id, claim.ticker.symbol, claim.as_of.isoformat(), claim.filing_id,
                claim.methodology_version, claim.category.value, claim.direction.value,
                claim.statement, claim.status.value, claim.method.value,
                json.dumps([_filing_ref_to_dict(item) for item in claim.source_references], sort_keys=True),
                claim.created_at.isoformat(), json.dumps(dict(claim.metadata), sort_keys=True),
            ),
        )

    def load_qualitative_claims(
        self, *, filing_id: str | None = None, ticker: Ticker | None = None
    ) -> tuple[QualitativeClaim, ...]:
        clauses: list[str] = []
        parameters: list[object] = []
        if filing_id is not None:
            clauses.append("filing_id = ?")
            parameters.append(filing_id)
        if ticker is not None:
            clauses.append("ticker = ?")
            parameters.append(ticker.symbol)
        query = "SELECT * FROM qualitative_claims"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY as_of, id"
        rows = self._connection.execute(query, tuple(parameters)).fetchall()
        return tuple(_qualitative_claim_from_row(row) for row in rows)

    def save_filing_section_change(self, change: FilingSectionChange) -> None:
        self._save_immutable(
            "filing_section_changes",
            "id",
            (
                "id", "ticker", "from_filing_id", "to_filing_id", "from_section_id",
                "to_section_id", "change_type", "methodology_version", "similarity",
                "material", "rationale", "source_references_json",
            ),
            (
                change.id, change.ticker.symbol, change.from_filing_id, change.to_filing_id,
                change.from_section_id, change.to_section_id, change.change_type.value,
                change.methodology_version, change.similarity, int(change.material),
                change.rationale,
                json.dumps([_filing_ref_to_dict(item) for item in change.source_references], sort_keys=True),
            ),
        )

    def load_filing_section_changes(self, ticker: Ticker) -> tuple[FilingSectionChange, ...]:
        rows = self._connection.execute(
            "SELECT * FROM filing_section_changes WHERE ticker = ? ORDER BY to_filing_id, id",
            (ticker.symbol,),
        ).fetchall()
        return tuple(_filing_change_from_row(row) for row in rows)

    def save_filing_evidence_snapshot(self, snapshot: FilingEvidenceSnapshot) -> None:
        self._save_immutable(
            "filing_evidence_snapshots",
            "id",
            (
                "id", "ticker", "as_of", "filing_ids_json", "section_ids_json",
                "claim_ids_json", "methodology_version", "created_at",
            ),
            (
                snapshot.id, snapshot.ticker.symbol, snapshot.as_of.isoformat(),
                json.dumps(snapshot.filing_ids), json.dumps(snapshot.section_ids),
                json.dumps(snapshot.claim_ids), snapshot.methodology_version,
                snapshot.created_at.isoformat(),
            ),
        )

    def load_filing_evidence_snapshot(self, snapshot_id: str) -> FilingEvidenceSnapshot | None:
        row = self._connection.execute(
            "SELECT * FROM filing_evidence_snapshots WHERE id = ?", (snapshot_id,)
        ).fetchone()
        if row is None:
            return None
        return FilingEvidenceSnapshot(
            row["id"], Ticker(row["ticker"]), date.fromisoformat(row["as_of"]),
            tuple(json.loads(row["filing_ids_json"])), tuple(json.loads(row["section_ids_json"])),
            tuple(json.loads(row["claim_ids_json"])), row["methodology_version"],
            datetime.fromisoformat(row["created_at"]),
        )

    def save_automation_definition(self, definition: ResearchAutomationDefinition) -> None:
        identity = f"{definition.id}@{definition.version}"
        self._save_immutable(
            "automation_definitions", "identity",
            (
                "identity", "definition_id", "version", "pipeline_version",
                "trigger_kinds_json", "strategy_name", "strategy_version",
                "universe_name", "schedule", "retry_policy_json", "enabled",
                "created_at", "parameters_json",
            ),
            (
                identity, definition.id, definition.version, definition.pipeline_version,
                json.dumps([kind.value for kind in definition.trigger_kinds]),
                definition.strategy_name, definition.strategy_version, definition.universe_name,
                definition.schedule,
                json.dumps(_retry_policy_to_dict(definition.retry_policy), sort_keys=True),
                int(definition.enabled), definition.created_at.isoformat(),
                json.dumps(dict(definition.parameters), sort_keys=True),
            ),
        )

    def load_automation_definition(
        self, definition_id: str, version: str
    ) -> ResearchAutomationDefinition | None:
        row = self._connection.execute(
            "SELECT * FROM automation_definitions WHERE definition_id = ? AND version = ?",
            (definition_id, version),
        ).fetchone()
        return _automation_definition_from_row(row) if row is not None else None

    def save_automation_trigger(self, trigger: AutomationTrigger) -> None:
        self._save_immutable(
            "automation_triggers", "id",
            (
                "id", "kind", "occurred_at", "as_of", "deduplication_key",
                "source_references_json", "tickers_json", "metadata_json",
            ),
            (
                trigger.id, trigger.kind.value, trigger.occurred_at.isoformat(),
                trigger.as_of.isoformat(), trigger.deduplication_key,
                json.dumps(
                    [_source_ref_to_dict(item) for item in trigger.source_references],
                    sort_keys=True,
                ),
                json.dumps([ticker.symbol for ticker in trigger.tickers]),
                json.dumps(dict(trigger.metadata), sort_keys=True),
            ),
        )

    def load_automation_trigger(self, trigger_id: str) -> AutomationTrigger | None:
        row = self._connection.execute(
            "SELECT * FROM automation_triggers WHERE id = ?", (trigger_id,)
        ).fetchone()
        return _automation_trigger_from_row(row) if row is not None else None

    def save_automation_run(self, run: AutomationRun) -> None:
        self._save_immutable(
            "automation_runs", "id",
            (
                "id", "definition_id", "definition_version", "pipeline_version",
                "trigger_id", "idempotency_key", "as_of", "status", "attempt",
                "created_at", "started_at", "finished_at", "steps_json",
                "source_references_json", "output_references_json",
            ),
            (
                run.id, run.definition_id, run.definition_version, run.pipeline_version,
                run.trigger_id, run.idempotency_key, run.as_of.isoformat(), run.status.value,
                run.attempt, run.created_at.isoformat(),
                run.started_at.isoformat() if run.started_at else None,
                run.finished_at.isoformat() if run.finished_at else None,
                json.dumps([_automation_step_to_dict(step) for step in run.steps], sort_keys=True),
                json.dumps(
                    [_source_ref_to_dict(item) for item in run.source_references], sort_keys=True
                ),
                json.dumps(
                    [_source_ref_to_dict(item) for item in run.output_references], sort_keys=True
                ),
            ),
        )

    def load_automation_run(self, run_id: str) -> AutomationRun | None:
        row = self._connection.execute(
            "SELECT * FROM automation_runs WHERE id = ?", (run_id,)
        ).fetchone()
        return _automation_run_from_row(row) if row is not None else None

    def automation_run_for_idempotency_key(self, key: str) -> AutomationRun | None:
        row = self._connection.execute(
            "SELECT * FROM automation_runs WHERE idempotency_key = ?", (key,)
        ).fetchone()
        return _automation_run_from_row(row) if row is not None else None

    def automation_runs(self, definition_id: str | None = None) -> tuple[AutomationRun, ...]:
        if definition_id is None:
            rows = self._connection.execute(
                "SELECT * FROM automation_runs ORDER BY as_of, created_at, id"
            ).fetchall()
        else:
            rows = self._connection.execute(
                "SELECT * FROM automation_runs WHERE definition_id = ? ORDER BY as_of, created_at, id",
                (definition_id,),
            ).fetchall()
        return tuple(_automation_run_from_row(row) for row in rows)

    def save_portfolio_construction_policy(self, policy: PortfolioConstructionPolicy) -> None:
        identity = f"{policy.name}@{policy.version}"
        self._save_immutable(
            "portfolio_construction_policies", "identity",
            (
                "identity", "name", "version", "weighting_method", "constraints_json",
                "transaction_cost_model", "transaction_cost_rate",
                "allow_fractional_shares", "parameters_json",
            ),
            (
                identity, policy.name, policy.version, policy.weighting_method.value,
                json.dumps([_portfolio_constraint_to_dict(item) for item in policy.constraints], sort_keys=True),
                policy.transaction_cost_model, policy.transaction_cost_rate,
                int(policy.allow_fractional_shares), json.dumps(dict(policy.parameters), sort_keys=True),
            ),
        )

    def load_portfolio_construction_policy(
        self, name: str, version: str
    ) -> PortfolioConstructionPolicy | None:
        row = self._connection.execute(
            "SELECT * FROM portfolio_construction_policies WHERE name = ? AND version = ?",
            (name, version),
        ).fetchone()
        return _portfolio_policy_from_row(row) if row is not None else None

    def save_portfolio_construction_request(self, request: PortfolioConstructionRequest) -> None:
        self._save_immutable(
            "portfolio_construction_requests", "id",
            (
                "id", "as_of", "research_run_id", "research_result_ids_json",
                "policy_name", "policy_version", "capital", "base_currency",
                "current_weights_json", "source_references_json",
            ),
            (
                request.id, request.as_of.isoformat(), request.research_run_id,
                json.dumps(request.research_result_ids), request.policy_name,
                request.policy_version, request.capital, request.base_currency,
                json.dumps([
                    {"ticker": item.ticker.symbol, "weight": item.weight}
                    for item in request.current_weights
                ], sort_keys=True),
                json.dumps([
                    _source_ref_to_dict(item) for item in request.source_references
                ], sort_keys=True),
            ),
        )

    def load_portfolio_construction_request(
        self, request_id: str
    ) -> PortfolioConstructionRequest | None:
        row = self._connection.execute(
            "SELECT * FROM portfolio_construction_requests WHERE id = ?", (request_id,)
        ).fetchone()
        return _portfolio_request_from_row(row) if row is not None else None

    def save_portfolio_construction_result(self, result: PortfolioConstructionResult) -> None:
        self._save_immutable(
            "portfolio_construction_results", "id",
            (
                "id", "request_id", "methodology_version", "status", "targets_json",
                "cash_weight", "gross_traded_notional", "turnover",
                "estimated_transaction_cost", "trades_json", "constraints_json",
                "source_references_json", "notes_json",
            ),
            (
                result.id, result.request_id, result.methodology_version, result.status.value,
                json.dumps([_target_position_to_dict(item) for item in result.targets], sort_keys=True),
                result.cash_weight, result.gross_traded_notional, result.turnover,
                result.estimated_transaction_cost,
                json.dumps([_trade_estimate_to_dict(item) for item in result.trades], sort_keys=True),
                json.dumps([_constraint_evaluation_to_dict(item) for item in result.constraints], sort_keys=True),
                json.dumps([_source_ref_to_dict(item) for item in result.source_references], sort_keys=True),
                json.dumps(result.notes),
            ),
        )

    def load_portfolio_construction_result(
        self, result_id: str
    ) -> PortfolioConstructionResult | None:
        row = self._connection.execute(
            "SELECT * FROM portfolio_construction_results WHERE id = ?", (result_id,)
        ).fetchone()
        return _portfolio_result_from_row(row) if row is not None else None

    def _save_immutable(
        self,
        table: str,
        identity_column: str,
        columns: tuple[str, ...],
        values: tuple[object, ...],
    ) -> None:
        placeholders = ", ".join("?" for _ in columns)
        column_sql = ", ".join(columns)
        self._connection.execute(
            f"INSERT OR IGNORE INTO {table} ({column_sql}) VALUES ({placeholders})", values
        )
        row = self._connection.execute(
            f"SELECT {column_sql} FROM {table} WHERE {identity_column} = ?", (values[0],)
        ).fetchone()
        if row is None or tuple(row[column] for column in columns) != values:
            self._connection.rollback()
            raise ValueError(f"immutable {table} identity conflicts with persisted content")
        self._connection.commit()

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        columns = {str(row[1]) for row in self._connection.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            self._connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def save_universe_snapshot(self, snapshot: UniverseSnapshot) -> None:
        self._connection.execute(
            """INSERT OR REPLACE INTO universe_snapshots
               (name, version, as_of, members_json, source, provenance_json, limitations_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (snapshot.name, snapshot.version, snapshot.as_of.isoformat(),
             json.dumps([member.symbol for member in snapshot.members]), snapshot.source,
             json.dumps([_provenance_to_dict(item) for item in snapshot.provenance], sort_keys=True),
             json.dumps([item.value for item in snapshot.limitations])),
        )
        self._connection.commit()

    def load_universe_snapshot(self, name: str, version: str) -> UniverseSnapshot | None:
        row = self._connection.execute(
            "SELECT * FROM universe_snapshots WHERE name = ? AND version = ?", (name, version)
        ).fetchone()
        if row is None:
            return None
        return UniverseSnapshot(
            row["name"], row["version"], date.fromisoformat(row["as_of"]),
            tuple(Ticker(symbol) for symbol in json.loads(row["members_json"])), row["source"],
            tuple(_provenance_from_dict(item) for item in json.loads(row["provenance_json"])),
            tuple(UniverseLimitation(item) for item in json.loads(row["limitations_json"])),
        )

    def save_raw_payload(
        self,
        *,
        provider: str,
        endpoint: str,
        parameters: dict[str, Any],
        payload: str,
        retrieved_at: datetime,
    ) -> str:
        """Store an exact payload and return its content-addressed identifier."""
        content_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        self._connection.execute(
            """INSERT OR IGNORE INTO raw_payloads
               (content_hash, provider, endpoint, parameters_json, payload, retrieved_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                content_hash,
                provider,
                endpoint,
                json.dumps(parameters, sort_keys=True),
                payload,
                retrieved_at.isoformat(),
            ),
        )
        self._connection.commit()
        return content_hash

    def save_observation(self, ticker: Ticker, observation: MetricObservation) -> int:
        self._connection.execute(
            """INSERT OR IGNORE INTO metric_observations
               (ticker, name, value, status, as_of, provenance_json, source_inputs_json, explanation)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                ticker.symbol,
                observation.name,
                observation.value,
                observation.status.value,
                observation.as_of.isoformat(),
                json.dumps(_provenance_to_dict(observation.provenance), sort_keys=True),
                json.dumps(observation.source_inputs),
                observation.explanation,
            ),
        )
        row = self._connection.execute(
            """SELECT id FROM metric_observations
               WHERE ticker = ? AND name = ? AND as_of = ? AND provenance_json = ?""",
            (
                ticker.symbol,
                observation.name,
                observation.as_of.isoformat(),
                json.dumps(_provenance_to_dict(observation.provenance), sort_keys=True),
            ),
        ).fetchone()
        self._connection.commit()
        if row is None:
            raise RuntimeError("observation was not persisted")
        return int(row["id"])

    def save_research_run(self, run: ResearchRun) -> None:
        self._connection.execute(
            """INSERT OR REPLACE INTO research_runs
               (id, created_at, as_of, strategy_name, strategy_version, universe_name,
                universe_version, universe_as_of, parameters_json, git_commit, data_snapshot, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run.id,
                run.created_at.isoformat(),
                run.as_of.isoformat(),
                run.strategy_name,
                run.strategy_version,
                run.universe_name,
                run.universe_version,
                run.universe_as_of.isoformat() if run.universe_as_of else None,
                json.dumps(run.parameters, sort_keys=True),
                run.git_commit,
                run.data_snapshot,
                run.status.value,
            ),
        )
        self._connection.commit()

    def save_research_result(self, result: ResearchResult) -> None:
        self._connection.execute(
            """INSERT OR REPLACE INTO research_results
               (id, run_id, ticker, created_at, rank, composite_score, classification,
                factor_scores_json, criteria_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                result.id,
                result.run_id,
                result.ticker.symbol,
                result.created_at.isoformat(),
                result.rank,
                result.composite_score,
                result.classification,
                json.dumps([_factor_score_to_dict(item) for item in result.factor_scores], sort_keys=True),
                json.dumps([_criterion_to_dict(item) for item in result.criteria], sort_keys=True),
            ),
        )
        self._connection.commit()

    def attach_observation(self, result_id: str, observation_id: int) -> None:
        self._connection.execute(
            "INSERT OR IGNORE INTO research_result_observations(result_id, observation_id) VALUES (?, ?)",
            (result_id, observation_id),
        )
        self._connection.commit()

    def save_research_outcome(self, outcome: ResearchOutcome) -> None:
        self._connection.execute(
            """INSERT OR REPLACE INTO research_outcomes
               (result_id, measured_at, horizon, forward_return, benchmark_return, excess_return)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (outcome.result_id, outcome.measured_at.isoformat(), outcome.horizon,
             outcome.forward_return, outcome.benchmark_return, outcome.excess_return),
        )
        self._connection.commit()

    def load_research_outcomes(self, result_id: str) -> tuple[ResearchOutcome, ...]:
        rows = self._connection.execute(
            "SELECT * FROM research_outcomes WHERE result_id = ? ORDER BY measured_at, horizon", (result_id,)
        ).fetchall()
        return tuple(ResearchOutcome(row["result_id"], date.fromisoformat(row["measured_at"]), row["horizon"],
                                     row["forward_return"], row["benchmark_return"], row["excess_return"])
                     for row in rows)

    def save_backtest_run(self, run: BacktestRun) -> None:
        config = {
            "start": run.config.start.isoformat(), "end": run.config.end.isoformat(),
            "top_n": run.config.top_n, "initial_capital": run.config.initial_capital,
            "transaction_cost_rate": run.config.transaction_cost_rate,
            "benchmark": run.config.benchmark, "corporate_action_mode": run.config.corporate_action_mode.value,
            "weighting_method": run.config.weighting_method, "selection_rule": run.config.selection_rule,
            "universe": run.config.universe, "rebalance_frequency": run.config.rebalance_frequency,
            "transaction_cost_model": run.config.transaction_cost_model,
            "return_convention": run.config.return_convention,
        }
        self._connection.execute(
            "INSERT OR REPLACE INTO backtest_runs(id, strategy_name, strategy_version, config_json, final_value, status) VALUES (?, ?, ?, ?, ?, ?)",
            (run.id, run.strategy_name, run.strategy_version, json.dumps(config, sort_keys=True), run.final_value, run.status),
        )
        self._connection.execute("DELETE FROM backtest_periods WHERE backtest_run_id = ?", (run.id,))
        for period in run.periods:
            self._connection.execute(
                """INSERT INTO backtest_periods
                   (backtest_run_id, period_index, research_run_id, rebalance_date, holding_start,
                    holding_end, starting_value, ending_value, gross_return, turnover,
                    transaction_cost, net_return, benchmark_return, excess_return,
                    selected_symbols_json, attribution_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (run.id, period.period_index, period.research_run_id, period.rebalance_date.isoformat(),
                 period.holding_start.isoformat(), period.holding_end.isoformat(), period.starting_value,
                 period.ending_value, period.gross_return, period.turnover, period.transaction_cost,
                 period.net_return, period.benchmark_return, period.excess_return,
                 json.dumps(period.selected_symbols), json.dumps([{
                     "symbol": item.symbol, "start_weight": item.start_weight,
                     "security_return": item.security_return, "contribution": item.contribution,
                 } for item in period.attribution], sort_keys=True)),
            )
        self._connection.commit()

    def load_backtest_run(self, run_id: str) -> BacktestRun | None:
        row = self._connection.execute("SELECT * FROM backtest_runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            return None
        config = json.loads(row["config_json"])
        config_obj = BacktestConfigV1(date.fromisoformat(config["start"]), date.fromisoformat(config["end"]),
                                      config["top_n"], config["initial_capital"], config["transaction_cost_rate"],
                                      config["benchmark"], CorporateActionMode(config["corporate_action_mode"]),
                                      config["weighting_method"], config["selection_rule"],
                                      config.get("universe", "unspecified"),
                                      config.get("rebalance_frequency", "research_run_schedule"),
                                      config.get("transaction_cost_model", "gross_traded_notional"),
                                      config.get("return_convention", "net_total_return"))
        rows = self._connection.execute("SELECT * FROM backtest_periods WHERE backtest_run_id = ? ORDER BY period_index", (run_id,)).fetchall()
        periods = tuple(BacktestPeriod(
            row_item["period_index"], row_item["research_run_id"], date.fromisoformat(row_item["rebalance_date"]),
            date.fromisoformat(row_item["holding_start"]), date.fromisoformat(row_item["holding_end"]),
            row_item["starting_value"], row_item["ending_value"], row_item["gross_return"], row_item["turnover"],
            row_item["transaction_cost"], row_item["net_return"], row_item["benchmark_return"], row_item["excess_return"],
            tuple(json.loads(row_item["selected_symbols_json"])),
            tuple(SecurityAttribution(item["symbol"], item["start_weight"], item["security_return"], item["contribution"])
                  for item in json.loads(row_item["attribution_json"])),
        ) for row_item in rows)
        return BacktestRun(row["id"], row["strategy_name"], row["strategy_version"], config_obj, periods, row["final_value"], row["status"])

    # Wave D capabilities intentionally live behind this one storage facade.
    def save_thesis_snapshot(self, snapshot: ThesisSnapshot) -> None:
        self._connection.execute(
            """INSERT OR REPLACE INTO thesis_snapshots
               (id, ticker, research_run_id, research_result_id, as_of, thesis_version,
                classification, summary, drivers_json, assumptions_json, invalidators_json,
                structured_views_json, confidence, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (snapshot.id, snapshot.ticker.symbol, snapshot.research_run_id, snapshot.research_result_id,
             snapshot.as_of.isoformat(), snapshot.thesis_version, snapshot.classification.value,
             snapshot.summary, json.dumps([_driver_to_dict(item) for item in snapshot.drivers], sort_keys=True),
             json.dumps([_assumption_to_dict(item) for item in snapshot.assumptions], sort_keys=True),
             json.dumps([_invalidator_to_dict(item) for item in snapshot.invalidators], sort_keys=True),
             json.dumps(snapshot.structured_views, sort_keys=True), snapshot.confidence,
             snapshot.created_at.isoformat() if snapshot.created_at else None),
        )
        self._connection.commit()

    def load_thesis_snapshot(self, snapshot_id: str) -> ThesisSnapshot | None:
        row = self._connection.execute("SELECT * FROM thesis_snapshots WHERE id = ?", (snapshot_id,)).fetchone()
        if row is None:
            return None
        return ThesisSnapshot(
            row["id"], Ticker(row["ticker"]), row["research_run_id"], row["research_result_id"],
            date.fromisoformat(row["as_of"]), row["thesis_version"], ThesisClassification(row["classification"]),
            row["summary"], tuple(_driver_from_dict(item) for item in json.loads(row["drivers_json"])),
            tuple(_assumption_from_dict(item) for item in json.loads(row["assumptions_json"])),
            tuple(_invalidator_from_dict(item) for item in json.loads(row["invalidators_json"])),
            json.loads(row["structured_views_json"]), row["confidence"],
            datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
        )

    def load_thesis_snapshots(self, ticker: Ticker) -> tuple[ThesisSnapshot, ...]:
        rows = self._connection.execute(
            "SELECT * FROM thesis_snapshots WHERE ticker = ? ORDER BY as_of, id", (ticker.symbol,)
        ).fetchall()
        return tuple(
            snapshot for row in rows
            if (snapshot := ThesisSnapshot(
                row["id"], Ticker(row["ticker"]), row["research_run_id"], row["research_result_id"],
                date.fromisoformat(row["as_of"]), row["thesis_version"], ThesisClassification(row["classification"]),
                row["summary"], tuple(_driver_from_dict(item) for item in json.loads(row["drivers_json"])),
                tuple(_assumption_from_dict(item) for item in json.loads(row["assumptions_json"])),
                tuple(_invalidator_from_dict(item) for item in json.loads(row["invalidators_json"])),
                json.loads(row["structured_views_json"]), row["confidence"],
                datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
            ))
        )

    def save_change_event(self, event: ResearchChangeEvent) -> int:
        self._connection.execute(
            """INSERT OR REPLACE INTO research_change_events
               (ticker, from_run_id, to_run_id, from_as_of, to_as_of, change_type, field,
                old_value_json, new_value_json, magnitude, materiality, source_references_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (event.ticker.symbol, event.from_run_id, event.to_run_id, event.from_as_of.isoformat(),
             event.to_as_of.isoformat(), event.change_type.value, event.field,
             json.dumps(event.old_value, sort_keys=True), json.dumps(event.new_value, sort_keys=True),
             event.magnitude, event.materiality,
             json.dumps([_source_ref_to_dict(item) for item in event.source_references], sort_keys=True)),
        )
        row = self._connection.execute(
            "SELECT id FROM research_change_events WHERE ticker=? AND from_run_id=? AND to_run_id=? AND change_type=? AND field=?",
            (event.ticker.symbol, event.from_run_id, event.to_run_id, event.change_type.value, event.field),
        ).fetchone()
        self._connection.commit()
        if row is None:
            raise RuntimeError("change event was not persisted")
        return int(row["id"])

    def load_change_events(self, ticker: Ticker | None = None) -> tuple[ResearchChangeEvent, ...]:
        query = "SELECT * FROM research_change_events"
        params: tuple[object, ...] = ()
        if ticker is not None:
            query += " WHERE ticker = ?"
            params = (ticker.symbol,)
        query += " ORDER BY from_as_of, to_as_of, id"
        rows = self._connection.execute(query, params).fetchall()
        return tuple(_change_event_from_row(row) for row in rows)

    def save_watchlist_entry(self, entry: WatchlistEntry) -> None:
        self._connection.execute(
            """INSERT OR REPLACE INTO watchlist_entries
               (id, ticker, created_at, source_run_id, source_result_id, reason, status,
                priority, tags_json, conditions_json, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (entry.id, entry.ticker.symbol, entry.created_at.isoformat(), entry.source_run_id,
             entry.source_result_id, entry.reason, entry.status.value, entry.priority,
             json.dumps(entry.tags), json.dumps([_condition_to_dict(item) for item in entry.target_conditions], sort_keys=True), entry.notes),
        )
        self._connection.commit()

    def load_watchlist_entry(self, entry_id: str) -> WatchlistEntry | None:
        row = self._connection.execute("SELECT * FROM watchlist_entries WHERE id = ?", (entry_id,)).fetchone()
        if row is None:
            return None
        return WatchlistEntry(row["id"], Ticker(row["ticker"]), datetime.fromisoformat(row["created_at"]),
                              row["source_run_id"], row["source_result_id"], row["reason"], WatchlistStatus(row["status"]),
                              row["priority"], tuple(json.loads(row["tags_json"])),
                              tuple(_condition_from_dict(item) for item in json.loads(row["conditions_json"])), row["notes"])

    def load_watchlist_entries(self) -> tuple[WatchlistEntry, ...]:
        rows = self._connection.execute("SELECT * FROM watchlist_entries ORDER BY created_at, id").fetchall()
        return tuple(
            WatchlistEntry(row["id"], Ticker(row["ticker"]), datetime.fromisoformat(row["created_at"]),
                           row["source_run_id"], row["source_result_id"], row["reason"], WatchlistStatus(row["status"]),
                           row["priority"], tuple(json.loads(row["tags_json"])),
                           tuple(_condition_from_dict(item) for item in json.loads(row["conditions_json"])), row["notes"])
            for row in rows
        )

    def save_monitoring_event(self, event: MonitoringEvent) -> int:
        self._connection.execute(
            """INSERT OR REPLACE INTO monitoring_events
               (watchlist_entry_id, research_run_id, as_of, condition_json, previous_state_json,
                current_state_json, triggered, rationale)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (event.watchlist_entry_id, event.research_run_id, event.as_of.isoformat(),
             json.dumps(_condition_to_dict(event.condition), sort_keys=True), json.dumps(event.previous_state, sort_keys=True),
             json.dumps(event.current_state, sort_keys=True), int(event.triggered), event.rationale),
        )
        row = self._connection.execute(
            "SELECT id FROM monitoring_events WHERE watchlist_entry_id=? AND research_run_id=? AND as_of=?",
            (event.watchlist_entry_id, event.research_run_id, event.as_of.isoformat()),
        ).fetchone()
        self._connection.commit()
        if row is None:
            raise RuntimeError("monitoring event was not persisted")
        return int(row["id"])

    def load_monitoring_events(self, entry_id: str) -> tuple[MonitoringEvent, ...]:
        rows = self._connection.execute("SELECT * FROM monitoring_events WHERE watchlist_entry_id=? ORDER BY as_of, id", (entry_id,)).fetchall()
        return tuple(MonitoringEvent(row["watchlist_entry_id"], row["research_run_id"], date.fromisoformat(row["as_of"]),
                                     _condition_from_dict(json.loads(row["condition_json"])), json.loads(row["previous_state_json"]),
                                     json.loads(row["current_state_json"]), bool(row["triggered"]), row["rationale"])
                     for row in rows)

    def save_factor_outcome_observation(self, observation: FactorOutcomeObservation) -> int:
        self._connection.execute(
            """INSERT OR REPLACE INTO factor_outcome_observations
               (factor_name, factor_version, research_run_id, ticker, as_of, factor_score,
                horizon, security_return, benchmark_return, excess_return, outcome_status,
                universe, benchmark, base_currency, rebalance_cadence)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (observation.factor_name, observation.factor_version, observation.research_run_id,
             observation.ticker.symbol, observation.as_of.isoformat(), observation.factor_score,
             observation.horizon, observation.security_return, observation.benchmark_return,
             observation.excess_return, observation.outcome_status, observation.universe,
             observation.benchmark, observation.base_currency, observation.rebalance_cadence),
        )
        row = self._connection.execute(
            """SELECT id FROM factor_outcome_observations
               WHERE research_run_id=? AND ticker=? AND factor_name=? AND factor_version=? AND horizon=?
                 AND universe=? AND benchmark=? AND base_currency=? AND rebalance_cadence=?""",
            (observation.research_run_id, observation.ticker.symbol, observation.factor_name,
             observation.factor_version, observation.horizon, observation.universe,
             observation.benchmark, observation.base_currency, observation.rebalance_cadence),
        ).fetchone()
        self._connection.commit()
        if row is None:
            raise RuntimeError("factor outcome observation was not persisted")
        return int(row["id"])

    def load_factor_outcome_observations(
        self, *, factor_name: str | None = None, factor_version: str | None = None
    ) -> tuple[FactorOutcomeObservation, ...]:
        clauses: list[str] = []
        params: list[object] = []
        if factor_name is not None:
            clauses.append("factor_name = ?")
            params.append(factor_name)
        if factor_version is not None:
            clauses.append("factor_version = ?")
            params.append(factor_version)
        query = "SELECT * FROM factor_outcome_observations"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY as_of, ticker, horizon"
        rows = self._connection.execute(query, tuple(params)).fetchall()
        return tuple(
            FactorOutcomeObservation(
                row["factor_name"], row["factor_version"], row["research_run_id"],
                Ticker(row["ticker"]), date.fromisoformat(row["as_of"]), row["factor_score"],
                row["horizon"], row["security_return"], row["benchmark_return"],
                row["excess_return"], row["outcome_status"], row["universe"], row["benchmark"],
                row["base_currency"], row["rebalance_cadence"],
            )
            for row in rows
        )

    def load_research_run(self, run_id: str) -> ResearchRun | None:
        row = self._connection.execute("SELECT * FROM research_runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            return None
        return ResearchRun(
            id=row["id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            as_of=date.fromisoformat(row["as_of"]),
            strategy_name=row["strategy_name"],
            strategy_version=row["strategy_version"],
            universe_name=row["universe_name"],
            universe_version=row["universe_version"],
            universe_as_of=date.fromisoformat(row["universe_as_of"]) if row["universe_as_of"] else None,
            parameters=json.loads(row["parameters_json"]),
            git_commit=row["git_commit"],
            data_snapshot=row["data_snapshot"],
            status=ResearchRunStatus(row["status"]),
        )

    def load_research_result(self, result_id: str) -> ResearchResult | None:
        row = self._connection.execute(
            "SELECT * FROM research_results WHERE id = ?", (result_id,)
        ).fetchone()
        if row is None:
            return None
        return ResearchResult(
            id=row["id"],
            run_id=row["run_id"],
            ticker=Ticker(row["ticker"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            rank=row["rank"],
            composite_score=row["composite_score"],
            classification=row["classification"],
            factor_scores=tuple(_factor_score_from_dict(item) for item in json.loads(row["factor_scores_json"] or "[]")),
            criteria=tuple(_criterion_from_dict(item) for item in json.loads(row["criteria_json"] or "[]")),
        )

    def load_research_results(self, run_id: str | None = None) -> tuple[ResearchResult, ...]:
        if run_id is None:
            rows = self._connection.execute("SELECT id FROM research_results ORDER BY created_at, id").fetchall()
        else:
            rows = self._connection.execute("SELECT id FROM research_results WHERE run_id = ? ORDER BY rank, ticker", (run_id,)).fetchall()
        return tuple(result for row in rows if (result := self.load_research_result(row["id"])) is not None)

    def load_backtest_runs(self) -> tuple[BacktestRun, ...]:
        rows = self._connection.execute("SELECT id FROM backtest_runs ORDER BY id").fetchall()
        return tuple(run for row in rows if (run := self.load_backtest_run(row["id"])) is not None)

    def load_result_observations(
        self, result_id: str, as_of: date
    ) -> tuple[MetricObservation, ...]:
        rows = self._connection.execute(
            """SELECT mo.* FROM metric_observations mo
               JOIN research_result_observations rro ON rro.observation_id = mo.id
               WHERE rro.result_id = ? AND mo.as_of <= ?
               ORDER BY mo.name""",
            (result_id, as_of.isoformat()),
        ).fetchall()
        return tuple(self._observation_from_row(row, as_of) for row in rows if self._is_visible(row, as_of))

    def load_observations(self, ticker: Ticker, as_of: date) -> tuple[MetricObservation, ...]:
        rows = self._connection.execute(
            "SELECT * FROM metric_observations WHERE ticker = ? AND as_of <= ? ORDER BY as_of, name",
            (ticker.symbol, as_of.isoformat()),
        ).fetchall()
        observations: list[MetricObservation] = []
        for row in rows:
            if not self._is_visible(row, as_of):
                continue
            observations.append(self._observation_from_row(row, as_of))
        return tuple(observations)

    @staticmethod
    def _is_visible(row: sqlite3.Row, as_of: date) -> bool:
        return _provenance_from_dict(json.loads(row["provenance_json"])).is_available_on(as_of)

    @staticmethod
    def _observation_from_row(row: sqlite3.Row, as_of: date) -> MetricObservation:
        provenance = _provenance_from_dict(json.loads(row["provenance_json"]))
        if not provenance.is_available_on(as_of):
            raise ValueError("attempted to materialize a future observation")
        return MetricObservation(
            name=row["name"],
            value=row["value"],
            status=MetricStatus(row["status"]),
            as_of=date.fromisoformat(row["as_of"]),
            provenance=provenance,
            source_inputs=tuple(json.loads(row["source_inputs_json"])),
            explanation=row["explanation"],
        )


def _provenance_to_dict(value: DataProvenance) -> dict[str, Any]:
    return {
        "source": value.source,
        "provider": value.provider,
        "retrieved_at": value.retrieved_at.isoformat(),
        "effective_date": value.effective_date.isoformat(),
        "period_end": value.period_end.isoformat() if value.period_end else None,
        "available_at": value.available_at.isoformat() if value.available_at else None,
        "filing_date": value.filing_date.isoformat() if value.filing_date else None,
        "period": {
            "start": value.period.start.isoformat(),
            "end": value.period.end.isoformat(),
            "kind": value.period.kind,
        }
        if value.period
        else None,
        "currency": value.currency,
        "units": value.units,
        "raw_identifier": value.raw_identifier,
        "derived": value.derived,
        "derivation_version": value.derivation_version,
    }


def _provenance_from_dict(value: dict[str, Any]) -> DataProvenance:
    period = value["period"]
    return DataProvenance(
        source=value["source"],
        provider=value["provider"],
        retrieved_at=datetime.fromisoformat(value["retrieved_at"]),
        effective_date=date.fromisoformat(value["effective_date"]),
        period_end=date.fromisoformat(value["period_end"]) if value.get("period_end") else None,
        available_at=datetime.fromisoformat(value["available_at"])
        if value["available_at"]
        else None,
        filing_date=date.fromisoformat(value["filing_date"]) if value["filing_date"] else None,
        period=Period(
            start=date.fromisoformat(period["start"]),
            end=date.fromisoformat(period["end"]),
            kind=period["kind"],
        )
        if period
        else None,
        currency=value["currency"],
        units=value["units"],
        raw_identifier=value["raw_identifier"],
        derived=value["derived"],
        derivation_version=value["derivation_version"],
    )


def _observation_to_dict(value: FactorObservation) -> dict[str, Any]:
    return {
        "name": value.name, "value": value.value, "status": value.status.value,
        "units": value.units, "as_of": value.as_of.isoformat(), "period": value.period,
        "calculation_version": value.calculation_version, "source_metric": value.source_metric,
        "source_provenance": [_provenance_to_dict(item) for item in value.source_provenance],
        "metadata": dict(value.metadata),
    }


def _observation_from_dict(value: dict[str, Any]) -> FactorObservation:
    return FactorObservation(
        value["name"], value["value"], AnalysisStatus(value["status"]), value["units"],
        date.fromisoformat(value["as_of"]), value["period"], value["calculation_version"],
        value.get("source_metric"), tuple(_provenance_from_dict(item) for item in value.get("source_provenance", [])),
        value.get("metadata", {}),
    )


def _factor_score_to_dict(value: FactorScore) -> dict[str, Any]:
    return {
        "factor_name": value.factor_name, "factor_version": value.factor_version,
        "score": value.score, "status": value.status.value, "weight": value.weight,
        "observations": [_observation_to_dict(item) for item in value.observations],
        "rationale": value.rationale,
    }


def _factor_score_from_dict(value: dict[str, Any]) -> FactorScore:
    return FactorScore(
        value["factor_name"], value["factor_version"], value["score"], AnalysisStatus(value["status"]),
        value["weight"], tuple(_observation_from_dict(item) for item in value["observations"]), value["rationale"],
    )


def _criterion_to_dict(value: CriterionResult) -> dict[str, Any]:
    return {
        "criterion_name": value.criterion_name, "criterion_version": value.criterion_version,
        "observed": value.observed, "threshold": value.threshold, "status": value.status.value,
        "passed": value.passed, "rationale": value.rationale,
        "source_observations": [_observation_to_dict(item) for item in value.source_observations],
    }


def _criterion_from_dict(value: dict[str, Any]) -> CriterionResult:
    return CriterionResult(
        value["criterion_name"], value["criterion_version"], value["observed"], value["threshold"],
        CriterionStatus(value["status"]), value["passed"], value["rationale"],
        tuple(_observation_from_dict(item) for item in value.get("source_observations", [])),
    )


def _source_ref_to_dict(value: SourceReference) -> dict[str, str | None]:
    return {"entity_type": value.entity_type, "entity_id": value.entity_id, "field": value.field}


def _source_ref_from_dict(value: dict[str, str | None]) -> SourceReference:
    return SourceReference(value["entity_type"] or "", value["entity_id"] or "", value.get("field"))


def _retry_policy_to_dict(value: RetryPolicy) -> dict[str, object]:
    return {
        "max_attempts": value.max_attempts,
        "initial_backoff_seconds": value.initial_backoff_seconds,
        "maximum_backoff_seconds": value.maximum_backoff_seconds,
        "retryable_failures": [item.value for item in value.retryable_failures],
    }


def _retry_policy_from_dict(value: dict[str, Any]) -> RetryPolicy:
    return RetryPolicy(
        value["max_attempts"], value["initial_backoff_seconds"],
        value["maximum_backoff_seconds"],
        tuple(AutomationFailureKind(item) for item in value["retryable_failures"]),
    )


def _automation_definition_from_row(row: sqlite3.Row) -> ResearchAutomationDefinition:
    return ResearchAutomationDefinition(
        row["definition_id"], row["version"], row["pipeline_version"],
        tuple(AutomationTriggerKind(item) for item in json.loads(row["trigger_kinds_json"])),
        row["strategy_name"], row["strategy_version"], row["universe_name"],
        row["schedule"], _retry_policy_from_dict(json.loads(row["retry_policy_json"])),
        bool(row["enabled"]), datetime.fromisoformat(row["created_at"]),
        json.loads(row["parameters_json"]),
    )


def _automation_trigger_from_row(row: sqlite3.Row) -> AutomationTrigger:
    return AutomationTrigger(
        row["id"], AutomationTriggerKind(row["kind"]),
        datetime.fromisoformat(row["occurred_at"]), date.fromisoformat(row["as_of"]),
        row["deduplication_key"],
        tuple(_source_ref_from_dict(item) for item in json.loads(row["source_references_json"])),
        tuple(Ticker(symbol) for symbol in json.loads(row["tickers_json"])),
        json.loads(row["metadata_json"]),
    )


def _automation_step_to_dict(value: AutomationStepResult) -> dict[str, object]:
    return {
        "step": value.step.value,
        "step_version": value.step_version,
        "status": value.status.value,
        "attempt": value.attempt,
        "started_at": value.started_at.isoformat(),
        "finished_at": value.finished_at.isoformat(),
        "input_references": [_source_ref_to_dict(item) for item in value.input_references],
        "output_references": [_source_ref_to_dict(item) for item in value.output_references],
        "failure_kind": value.failure_kind.value if value.failure_kind else None,
        "error_message": value.error_message,
        "retryable": value.retryable,
    }


def _automation_step_from_dict(value: dict[str, Any]) -> AutomationStepResult:
    failure = value.get("failure_kind")
    return AutomationStepResult(
        AutomationStepName(value["step"]), value["step_version"],
        AutomationStepStatus(value["status"]), value["attempt"],
        datetime.fromisoformat(value["started_at"]),
        datetime.fromisoformat(value["finished_at"]),
        tuple(_source_ref_from_dict(item) for item in value["input_references"]),
        tuple(_source_ref_from_dict(item) for item in value["output_references"]),
        AutomationFailureKind(failure) if failure else None, value.get("error_message"),
        bool(value.get("retryable", False)),
    )


def _automation_run_from_row(row: sqlite3.Row) -> AutomationRun:
    return AutomationRun(
        row["id"], row["definition_id"], row["definition_version"],
        row["pipeline_version"], row["trigger_id"], row["idempotency_key"],
        date.fromisoformat(row["as_of"]), AutomationRunStatus(row["status"]),
        row["attempt"], datetime.fromisoformat(row["created_at"]),
        datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
        datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None,
        tuple(_automation_step_from_dict(item) for item in json.loads(row["steps_json"])),
        tuple(_source_ref_from_dict(item) for item in json.loads(row["source_references_json"])),
        tuple(_source_ref_from_dict(item) for item in json.loads(row["output_references_json"])),
    )


def _portfolio_constraint_to_dict(value: PortfolioConstraint) -> dict[str, object]:
    return {
        "kind": value.kind.value,
        "limit": value.limit,
        "version": value.version,
        "scope": value.scope,
    }


def _portfolio_constraint_from_dict(value: dict[str, Any]) -> PortfolioConstraint:
    return PortfolioConstraint(
        PortfolioConstraintKind(value["kind"]), value["limit"], value["version"], value["scope"]
    )


def _portfolio_policy_from_row(row: sqlite3.Row) -> PortfolioConstructionPolicy:
    return PortfolioConstructionPolicy(
        row["name"], row["version"], WeightingMethod(row["weighting_method"]),
        tuple(_portfolio_constraint_from_dict(item) for item in json.loads(row["constraints_json"])),
        row["transaction_cost_model"], row["transaction_cost_rate"],
        bool(row["allow_fractional_shares"]), json.loads(row["parameters_json"]),
    )


def _portfolio_request_from_row(row: sqlite3.Row) -> PortfolioConstructionRequest:
    return PortfolioConstructionRequest(
        row["id"], date.fromisoformat(row["as_of"]), row["research_run_id"],
        tuple(json.loads(row["research_result_ids_json"])), row["policy_name"],
        row["policy_version"], row["capital"], row["base_currency"],
        tuple(
            CurrentPortfolioWeight(Ticker(item["ticker"]), item["weight"])
            for item in json.loads(row["current_weights_json"])
        ),
        tuple(_source_ref_from_dict(item) for item in json.loads(row["source_references_json"])),
    )


def _target_position_to_dict(value: TargetPosition) -> dict[str, object]:
    return {
        "ticker": value.ticker.symbol,
        "target_weight": value.target_weight,
        "source_result_id": value.source_result_id,
        "source_score": value.source_score,
        "rationale": value.rationale,
    }


def _target_position_from_dict(value: dict[str, Any]) -> TargetPosition:
    return TargetPosition(
        Ticker(value["ticker"]), value["target_weight"], value["source_result_id"],
        value["source_score"], value["rationale"],
    )


def _trade_estimate_to_dict(value: TradeEstimate) -> dict[str, object]:
    return {
        "ticker": value.ticker.symbol,
        "current_weight": value.current_weight,
        "target_weight": value.target_weight,
        "weight_delta": value.weight_delta,
        "traded_notional": value.traded_notional,
        "estimated_cost": value.estimated_cost,
    }


def _trade_estimate_from_dict(value: dict[str, Any]) -> TradeEstimate:
    return TradeEstimate(
        Ticker(value["ticker"]), value["current_weight"], value["target_weight"],
        value["weight_delta"], value["traded_notional"], value["estimated_cost"],
    )


def _constraint_evaluation_to_dict(value: ConstraintEvaluation) -> dict[str, object]:
    return {
        "kind": value.kind.value,
        "scope": value.scope,
        "observed": value.observed,
        "limit": value.limit,
        "status": value.status.value,
        "rationale": value.rationale,
    }


def _constraint_evaluation_from_dict(value: dict[str, Any]) -> ConstraintEvaluation:
    return ConstraintEvaluation(
        PortfolioConstraintKind(value["kind"]), value["scope"], value["observed"],
        value["limit"], ConstraintStatus(value["status"]), value["rationale"],
    )


def _portfolio_result_from_row(row: sqlite3.Row) -> PortfolioConstructionResult:
    return PortfolioConstructionResult(
        row["id"], row["request_id"], row["methodology_version"],
        ConstructionStatus(row["status"]),
        tuple(_target_position_from_dict(item) for item in json.loads(row["targets_json"])),
        row["cash_weight"], row["gross_traded_notional"], row["turnover"],
        row["estimated_transaction_cost"],
        tuple(_trade_estimate_from_dict(item) for item in json.loads(row["trades_json"])),
        tuple(
            _constraint_evaluation_from_dict(item)
            for item in json.loads(row["constraints_json"])
        ),
        tuple(_source_ref_from_dict(item) for item in json.loads(row["source_references_json"])),
        tuple(json.loads(row["notes_json"])),
    )


def _driver_to_dict(value: ThesisDriver) -> dict[str, Any]:
    return {"name": value.name, "category": value.category.value, "direction": value.direction.value,
            "importance": value.importance, "current_state": value.current_state,
            "source_reference": _source_ref_to_dict(value.source_reference), "rationale": value.rationale}


def _driver_from_dict(value: dict[str, Any]) -> ThesisDriver:
    return ThesisDriver(value["name"], ThesisDriverCategory(value["category"]), DriverDirection(value["direction"]),
                        value["importance"], value["current_state"], _source_ref_from_dict(value["source_reference"]), value["rationale"])


def _assumption_to_dict(value: ThesisAssumption) -> dict[str, Any]:
    return {"name": value.name, "description": value.description, "status": value.status,
            "source_reference": _source_ref_to_dict(value.source_reference)}


def _assumption_from_dict(value: dict[str, Any]) -> ThesisAssumption:
    return ThesisAssumption(value["name"], value["description"], value["status"], _source_ref_from_dict(value["source_reference"]))


def _invalidator_to_dict(value: ThesisInvalidator) -> dict[str, Any]:
    return {"name": value.name, "condition": value.condition, "severity": value.severity,
            "source_reference": _source_ref_to_dict(value.source_reference)}


def _invalidator_from_dict(value: dict[str, Any]) -> ThesisInvalidator:
    return ThesisInvalidator(value["name"], value["condition"], value["severity"], _source_ref_from_dict(value["source_reference"]))


def _condition_to_dict(value: WatchCondition) -> dict[str, Any]:
    return {"subject": value.subject, "operator": value.operator, "threshold": value.threshold,
            "version": value.version, "status": value.status}


def _condition_from_dict(value: dict[str, Any]) -> WatchCondition:
    return WatchCondition(value["subject"], value["operator"], value["threshold"], value["version"], value.get("status", "active"))


def _change_event_from_row(row: sqlite3.Row) -> ResearchChangeEvent:
    return ResearchChangeEvent(
        Ticker(row["ticker"]), row["from_run_id"], row["to_run_id"], date.fromisoformat(row["from_as_of"]),
        date.fromisoformat(row["to_as_of"]), ChangeType(row["change_type"]), row["field"],
        json.loads(row["old_value_json"]), json.loads(row["new_value_json"]), row["magnitude"], row["materiality"],
        tuple(_source_ref_from_dict(item) for item in json.loads(row["source_references_json"])),
    )


def _filing_ref_to_dict(value: FilingEvidenceReference) -> dict[str, object]:
    return {
        "filing_id": value.filing_id,
        "section_id": value.section_id,
        "source_start": value.source_start,
        "source_end": value.source_end,
        "excerpt_hash": value.excerpt_hash,
    }


def _filing_ref_from_dict(value: dict[str, Any]) -> FilingEvidenceReference:
    return FilingEvidenceReference(
        value["filing_id"], value["section_id"], value["source_start"],
        value["source_end"], value["excerpt_hash"],
    )


def _filing_document_from_row(row: sqlite3.Row) -> FilingDocument:
    return FilingDocument(
        row["id"], Ticker(row["ticker"]), row["cik"], row["accession_number"],
        FilingForm(row["form"]), datetime.fromisoformat(row["filed_at"]),
        datetime.fromisoformat(row["available_at"]),
        date.fromisoformat(row["period_end"]) if row["period_end"] else None,
        row["primary_document"], row["source_url"], row["content_hash"],
        datetime.fromisoformat(row["retrieved_at"]), row["mime_type"], row["size_bytes"],
        _provenance_from_dict(json.loads(row["provenance_json"])),
    )


def _filing_section_from_row(row: sqlite3.Row) -> FilingSection:
    return FilingSection(
        row["id"], row["filing_id"], row["item"], row["title"],
        FilingSectionKind(row["kind"]), row["ordinal"], row["normalized_text"],
        row["content_hash"], row["source_start"], row["source_end"],
        row["parser_version"], json.loads(row["metadata_json"]),
    )


def _qualitative_claim_from_row(row: sqlite3.Row) -> QualitativeClaim:
    return QualitativeClaim(
        row["id"], Ticker(row["ticker"]), date.fromisoformat(row["as_of"]), row["filing_id"],
        row["methodology_version"], ClaimCategory(row["category"]),
        ClaimDirection(row["direction"]), row["statement"], ClaimStatus(row["status"]),
        ClaimMethod(row["method"]),
        tuple(_filing_ref_from_dict(item) for item in json.loads(row["source_references_json"])),
        datetime.fromisoformat(row["created_at"]), json.loads(row["metadata_json"]),
    )


def _filing_change_from_row(row: sqlite3.Row) -> FilingSectionChange:
    return FilingSectionChange(
        row["id"], Ticker(row["ticker"]), row["from_filing_id"], row["to_filing_id"],
        row["from_section_id"], row["to_section_id"], FilingChangeType(row["change_type"]),
        row["methodology_version"], row["similarity"], bool(row["material"]),
        row["rationale"],
        tuple(_filing_ref_from_dict(item) for item in json.loads(row["source_references_json"])),
    )
