# Legacy call graph

## Runtime roots

    mainCode/Algotrading.py
      -> stock(ticker, days=400)
         -> Technical_Analysis.__init__ -> stock.historic_data -> Yahoo DataReader
      -> print(trade_history)

    mainCode/value_investment_lookup.py:main
      -> email_information('../../email_passwd.init')
      -> Gsheet(sheet_link) [missing sibling module]
      -> get*TickerList() [FTP/Wikipedia]
      -> defensive_investor_portafolio -> stock -> Yahoo/FMP methods
      -> valueStocks -> Gsheet.append

    mainCode/Investment_value.py:main
      -> Gsheet(MAINSPREADSHEET_ID) [missing sibling module]
      -> Book DataFrame -> stock -> Investment_data
      -> pandas.Panel -> plots of value minus principal

    mainCode/Tradebill_Library.py:84
      -> wsbMomentum('GME') -> daily/weekly stock -> Impulse_System -> EMA/MACD
      [unreachable: syntax error at line 10]

    Test scripts
      -> test_fundamentals -> YahooFinancials live calls
      -> Yahoo_datareader -> FMP live request
      -> Test_EDGAR -> missing edgar package
      -> ETF_data -> missing ticker_ETF.txt -> stock/network/plots
      -> expected_requirements -> investing optimizer/plots

## Central object

stock.__init__ calls both parent constructors (mainCode/stock.py:1568-1576). The technical parent calls historic_data before returning reshaped trade_history (mainCode/stock.py:963-1005), and the fundamental parent creates YahooFinancials (mainCode/stock.py:105-110). Any stock construction inherits remote I/O and current provider schemas.

## Fundamental and strategy flow

profile, balance, income, cash, ratios and metrics populate mutable attributes (mainCode/stock.py:112-155). Fetchers build FMP URLs and convert values to Decimal (mainCode/stock.py:744-827); __webData performs unchecked requests.get(...).json() (mainCode/stock.py:958-961). EV is market cap + debt - cash (mainCode/stock.py:167-188), book value is a current-assets approximation (mainCode/stock.py:217-240), EPS is net income divided by one share-count value (mainCode/stock.py:374-411), and dividends come from FMP (mainCode/stock.py:612-652).

The defensive screen applies price, current ratio, PE, price/book, revenue, EPS stability/growth and optional dividends (mainCode/value_investment_lookup.py:11-182), then writes selected values to Sheets (mainCode/value_investment_lookup.py:184-213). The momentum score intends daily/weekly impulse, EMA zone, MACD histogram shape and price direction (mainCode/Tradebill_Library.py:18-71), but cannot be imported.

## Broken edges

- historic_data computes start_date but passes from_date to DataReader, so the default is unused (mainCode/stock.py:1578-1587).
- Investment_value uses missing Gsheet (mainCode/Investment_value.py:6-7, 73-77), DataFrame.append and pandas.Panel (mainCode/Investment_value.py:128-145).
- value_investment_lookup compares strings with is (mainCode/value_investment_lookup.py:226-293).
- priceGraham references undefined timeline (mainCode/stock.py:583-590); RSI rejects default Close because it checks lowercase close (mainCode/stock.py:1191-1194); Bolli_Bands references undefined names (mainCode/stock.py:1227-1247).
