# E4 — Auditoría de dependencias para construcción avanzada de carteras

Estado: `REVIEW` — auditoría documental completada; no se modifica producción.

## Alcance y conclusión

E4 debe añadir una capa determinista de construcción de cartera que transforme
señales de investigación ya validadas en una asignación objetivo y, después,
en un plan de operaciones/rebalanceo. No debe volver a calcular métricas,
estrategias ni contabilidad.

La frontera recomendada es:

```text
ResearchRun / ResearchResult persistidos
        ↓
PortfolioConstructionInput (señales + restricciones + precios/contexto)
        ↓
PortfolioConstructionResult (target weights + diagnostics + rationale)
        ↓
RebalancePlan (identity-safe trades + estimated turnover/cost)
        ↓
Transaction[] / Backtest portfolio state
        ↓
PortfolioLedger o C6 BacktestRun
```

El resultado de construcción es una decisión de asignación. El ledger sigue
siendo la autoridad para cash, lotes, posiciones, coste, P&L y acciones
corporativas; C6 sigue siendo la autoridad para simular períodos y persistir
el resultado histórico.

## Componentes reutilizables

### Investigación, scoring y screening

- `domain.research.ResearchRun` identifica `strategy_name`,
  `strategy_version`, `as_of`, universo/versiones, parámetros y snapshot de
  datos. Es la identidad histórica que E4 debe conservar.
- `domain.research.ResearchResult` contiene ticker, rank, score compuesto,
  clasificación, `FactorScore[]`, `CriterionResult[]` y referencias a
  observaciones. Es la entrada natural para selección y pesos basados en
  señales.
- `domain.research_engine.FactorScore` conserva factor/version, score 0–100,
  estado, peso, observaciones y rationale. E4 debe consumirlo; no debe
  reconstruirlo desde datos brutos.
- `domain.research_engine.CompositeScore` conserva componentes, pesos,
  política de missing data, versión de estrategia y `as_of`. Sirve para
  estrategias de peso por score, con una política explícita para valores
  ausentes.
- `screening.engine.ScreeningSelection` ya materializa ticker, rank, score,
  estado, criterios, observaciones y factor scores.
- `screening.engine.ScreeningRun` agrupa `ResearchRun`, `UniverseSnapshot` y
  selecciones. E4 debe recibir este artefacto o sus equivalentes cargados desde
  persistencia, no una lista reordenada sin identidad.
- `screening.engine.ScreeningEngine` ya filtra y ordena candidatos de forma
  determinista y persiste `ResearchRun`/`ResearchResult`. Debe preceder a E4.
- `scoring.engine.ScoringEngine`, `score_factor` y `compose` son cálculos
  puros. E4 no debe duplicar normalización ni introducir pesos dentro del
  scoring de investigación.

### Contabilidad y posiciones

- `portfolio.models.Transaction` es el evento contable canónico. Soporta
  `BUY`, `SELL`, `DIVIDEND`, `FEE`, `TAX`, `SPLIT`, transferencias y entradas o
  salidas de cash, además de cantidades fraccionarias, precio, fee y moneda.
- `portfolio.models.Position` representa cantidad, coste, moneda, P&L
  realizado y precio de mercado; `PortfolioState` representa cash, posiciones,
  valor de mercado y valor total.
- `portfolio.ledger.PortfolioLedger` es un ledger append-only con lotes FIFO.
  `reconstruct(as_of, prices, fx_rates)` aplica transacciones y devuelve
  `PortfolioState`. E4 no debe mutar lotes, recalcular coste ni crear una
  contabilidad paralela.
- La conversión de un plan de rebalanceo a transacciones debe ser un adaptador
  estrecho y explícito. El adaptador deberá preservar el orden/fecha y crear
  `BUY`/`SELL`/`FEE` con identidad estable; la validación final de cash y
  posiciones debe ocurrir al pasar por `PortfolioLedger`.

### Simulación y outcomes

- `backtesting.engine.BacktestConfigV1` ya fija top-N, capital inicial,
  frecuencia, universo, selección, weighting, coste, benchmark, convención de
  retorno y política de acciones corporativas.
- `BacktestRun` y `BacktestPeriod` son los artefactos persistibles de C6. Cada
  período conserva `research_run_id`, fechas, valores, retornos bruto/neto,
  turnover, coste, benchmark, exceso, símbolos seleccionados y atribución por
  security.
- `simulate_persisted_runs` consume `ResearchRun`/`ResearchResult` congelados y
  conserva los símbolos por clave. E4 no debe volver a seleccionar ni rerunear
  la estrategia. Para una futura integración, el backtester debe consumir el
  `PortfolioConstructionResult` registrado o un plan equivalente versionado.
- `rebalance_metrics` ya calcula notional negociado, turnover, coste e importe
  invertible por identidad. E4 puede reutilizarlo para diagnosticar una
  asignación, pero C6/ledger debe seguir siendo la autoridad del efecto
  monetario real.
- `simulate_equal_weight` y `scores_from_persisted_results` son puentes V1.
  El primero no es suficiente para restricciones avanzadas; el segundo es un
  puente adecuado para recuperar decisiones persistidas, no para generar una
  nueva señal.

### Analytics

`analytics.performance` contiene funciones puras de retorno, TWR, XIRR,
drawdown, volatilidad, beta, alpha y retorno relativo. E4 no debe duplicarlas.
La construcción puede estimar riesgo/turnover para seleccionar una asignación,
pero la medición realizada debe seguir en analytics/C6.

## Dependencias faltantes mínimas

No se necesita un contenedor de servicios nuevo. E4 necesita contratos
pequeños y versionados, preferiblemente en `domain/` e `interfaces/`, antes de
implementar algoritmos:

1. `PortfolioConstructionInput`:
   - `research_run_id`, `as_of`, estrategia/version y universo/version;
   - señales por ticker, idealmente referencias a `ResearchResult` y
     `FactorScore` persistidos;
   - estado de cartera previo, precios disponibles y moneda base;
   - restricciones y política de datos faltantes.
2. `PortfolioConstructionPolicy`:
   - método/version (`equal_weight_v1`, `score_weighted_v1`, etc.);
   - límites por posición, sector y exposición;
   - objetivo de volatilidad/riesgo si se soporta;
   - penalización o límite de turnover;
   - política explícita de infeasibility (`FAIL` o resultado insuficiente).
3. `PortfolioConstructionResult`:
   - pesos objetivo por ticker, siempre keyed por identidad;
   - score/diagnóstico por restricción y razones de exclusión;
   - suma de pesos, cash residual y estado;
   - referencias a run/result/factor inputs y versión del método.
4. `RebalancePlan`:
   - fecha y cartera pre-trade;
   - trades por ticker con cantidad/notional y side;
   - turnover, coste estimado, moneda y política de coste;
   - referencia al `PortfolioConstructionResult`.
5. Una interfaz mínima tipo `PortfolioConstructor.construct(...)` y un
   adaptador separado tipo `RebalancePlanner.plan(...)`. Ninguno debe conocer
   proveedores HTTP o ejecutar SQL.

### Decisiones que deben congelarse antes de implementar

- Si los pesos se calculan sobre valor pre-coste y el coste se descuenta antes
  de comprar, o si se reserva cash para coste antes de formar objetivos.
- Convención de turnover: notional bruto de compras+ventas y su relación con
  el coste, sin confundirlo con la convención media de pesos.
- Tratamiento de posiciones existentes que salen de la selección: liquidación
  en rebalanceo, permanencia o límites de venta.
- Semántica de cash residual, lotes fraccionarios, divisas y redondeo.
- Si los límites sectoriales exigen que `CompanyProfile`/sector sea una
  dependencia obligatoria o un input opcional con estado `INSUFFICIENT_DATA`.
- Si una acción corporativa se representa por transacciones explícitas o por
  precios ajustados; no se permite mezclar ambas semánticas.

## Flujo de construcción propuesto

1. Cargar un `ResearchRun` y sus `ResearchResult` desde SQLite.
2. Validar estrategia/version, universo/version, `as_of` y moneda.
3. Extraer señales ya persistidas por ticker y conservar sus referencias.
4. Cargar estado pre-trade mediante `PortfolioLedger.reconstruct` o estado
   histórico equivalente.
5. Ejecutar un constructor puro y determinista con política versionada.
6. Validar que pesos sean identity-safe, no negativos salvo que se soporte
   shorting explícito, y respeten límites; registrar exclusiones y faltantes.
7. Convertir objetivos a `RebalancePlan`, calculando trades por diferencia de
   valor y precios de la misma fecha.
8. Aplicar el plan como transacciones al ledger o como operaciones del
   backtest. No mutar directamente `PortfolioState`.
9. Persistir el vínculo entre decisión de construcción, `ResearchRun`, plan,
   período de backtest y cualquier ledger batch.
10. Medir resultados con analytics/C6 después del hecho. Esos resultados no
    vuelven a la entrada de construcción histórica.

## Riesgos y controles

- **Look-ahead:** sólo aceptar señales cuyo `as_of` y disponibilidad PIT sean
  compatibles con el rebalanceo; no usar precios posteriores para formar la
  cartera.
- **Pérdida de identidad:** usar mappings keyed por ticker y ordenar sólo para
  serialización. Prohibir paralelismo posicional entre símbolos, precios y
  pesos.
- **Doble contabilidad:** E4 emite plan/órdenes; `PortfolioLedger` aplica cash,
  fees, lotes y splits una sola vez.
- **Doble coste:** elegir una única autoridad para el coste del rebalanceo.
  Si C6 lo registra en `BacktestPeriod`, no añadir además un `FEE` duplicado al
  estado simulado sin documentarlo.
- **Shorting implícito:** pesos negativos deben rechazarse en V1 si no hay
  contrato específico de margen y borrowing.
- **Universe leakage:** no usar la membresía actual; validar el
  `UniverseSnapshot` asociado al `ResearchRun`.
- **Moneda:** pesos pueden ser adimensionales, pero notional, cash y precios
  deben compartir moneda o incorporar una conversión explícita con
  provenance.
- **Infeasibility silenciosa:** restricciones imposibles deben devolver estado
  explícito, no pesos recortados sin explicación.
- **Reproducibilidad:** persistir método/version, parámetros, snapshot,
  research-run y configuración de costes.

## Cómo alimenta E4 al ledger y a C6 sin duplicar accounting

### Ledger real / reconstrucción de cartera

`PortfolioConstructor` produce pesos objetivo. `RebalancePlanner` compara esos
pesos con `PortfolioState.positions`, calcula notional por ticker y produce
transacciones normalizadas. Un adaptador convierte cada compra/venta a
`Transaction` con fecha, símbolo, cantidad, precio, moneda y fee. El único
camino que actualiza cash, FIFO, coste y P&L es:

```text
PortfolioConstructionResult
  → RebalancePlan
  → Transaction[]
  → PortfolioLedger.add/extend
  → PortfolioLedger.reconstruct
```

No se debe introducir un `ConstructedPortfolio` que reimplemente lotes o cash.

### Backtest

En cada fecha de rebalanceo, C6 carga el `ResearchRun` persistido y el
`PortfolioConstructionResult`/plan asociado. C6 obtiene precios PIT para
convertir pesos a cantidades, aplica el coste una sola vez, guarda
`BacktestPeriod` y mantiene `research_run_id` como lineage. El backtest puede
usar el plan para simular; no llama al constructor con datos actuales ni
recalcula scores.

Si E4 aún no tiene persistencia propia, V1 puede persistir el resultado como
artefacto derivado versionado junto al `BacktestRun` o mediante un callback del
facade existente. No se debe crear un `PortfolioConstructionStorageBackend`
aislado sin revisar antes el facade de SQLite.

## Propuesta de ownership y valla

### Arquitectura / contratos

`src/stocks_investment/domain/portfolio_construction.py`,
`src/stocks_investment/interfaces/portfolio_construction.py` y
`docs/architecture/`.

Responsable: Program Lead/Chief Architect. Ningún agente de algoritmo puede
editar estos paths; cualquier cambio debe ser una solicitud de contrato.

### Constructor de pesos

`src/stocks_investment/construction/`,
`tests/construction/`, `docs/methodology/portfolio-construction/`.

Implementa políticas puras de score-weighted, límites y restricciones.
No modifica portfolio, analytics, backtesting, storage ni CLI.

### Planner / integración de operaciones

`src/stocks_investment/rebalancing/`, `tests/rebalancing/`,
`docs/methodology/rebalancing/`.

Convierte pesos a trades identity-safe. No implementa FIFO, cash accounting ni
performance.

### Integración C6

`src/stocks_investment/backtesting/` y `tests/backtesting/`, únicamente para el
adaptador que consume resultados/planes persistidos. El Integrator es el único
que puede modificar esta zona durante la integración.

### Persistencia

`src/stocks_investment/storage/`, `tests/storage/` sólo por el Integrator,
después de aprobar el esquema mínimo. Preferir una migración aditiva y no un
protocolo nuevo.

### Ledger y analytics

`src/stocks_investment/portfolio/` y `src/stocks_investment/analytics/` quedan
fuera de ownership de los agentes E4 salvo tests de contrato coordinados. Si
se detecta una insuficiencia real, abrir solicitud de cambio y no parchear
contabilidad desde construcción.

### Tests de integración / adversariales

`tests/integration/`, `tests/e2e/`, `docs/validation/` pertenecen al Integrator.
Deben verificar PIT, identidad, costes, restricciones inviables, cash, split,
DB reopen, determinismo y ausencia de proveedor.

## Criterios de aceptación de la arquitectura E4

- La construcción consume `ResearchResult`/`FactorScore` persistidos y no
  produce nuevas señales.
- El constructor es puro, deterministicamente versionado y provider-free.
- Pesos, trades y atribuciones mantienen ticker identity.
- Restricciones, faltantes, cash residual y costes tienen estados explícitos.
- El plan puede materializarse como transacciones sin duplicar ledger.
- C6 puede simular el plan conservando `ResearchRun` → construcción → período.
- Un cierre/reapertura de SQLite conserva parámetros, referencias y resultados.
- No se marca E4 como validado hasta contar con pruebas independientes de
  construcción, integración con ledger, integración C6, moneda, costes,
  acciones corporativas, información PIT y reproducibilidad.

## Recomendación

Congelar primero los cinco contratos mínimos (input, policy, result, plan y
constructor/planner). Implementar inicialmente score-weighted con límites de
posición y un planner de rebalanceo sin shorts. Dejar optimización media-varianza,
risk-parity y volatilidad objetivo fuera de la primera entrega. Validar que la
salida se pueda convertir en transacciones del ledger y en `BacktestPeriod`
sin duplicar ni alterar las fórmulas financieras ya validadas.
