# V2 domain model

Core value objects: `Ticker`, `Instrument`, `Exchange`, `Currency`, `DateRange`, `FinancialPeriod`, `Unit`, and `DataProvenance`.

Core observations: `PriceBar`, `Quote`, `CorporateAction`, `FinancialStatement`, `MetricObservation`, `FundamentalSnapshot`, and `TechnicalSnapshot`.

Decision objects: `ScoreComponent`, `Score`, `ScreenResult`, `StrategyDefinition`, `ResearchRun`, and `InvestmentThesis`.

Accounting objects: `Transaction`, `Position`, `PortfolioSnapshot`, `Benchmark`, and `BacktestRun`.

Every derived object carries a derivation version and references its input observations. Domain objects are typed; arbitrary provider dictionaries stop at adapter boundaries.
