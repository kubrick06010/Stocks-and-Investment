import json
from datetime import date

from stocks_investment.data.providers import SecEdgarProvider
from stocks_investment.data.providers._http import HttpResponse
from stocks_investment.domain import Period, Ticker
from stocks_investment.fundamentals import calculate_metric, fact_from_observation
from stocks_investment.storage import SQLiteStorage


def test_sec_adapter_to_storage_preserves_filing_availability(tmp_path) -> None:
    def transport(url: str, headers: dict[str, str], timeout: float) -> HttpResponse:
        return HttpResponse(
            json.dumps(
                {
                    "facts": {
                        "us-gaap": {
                            "Revenues": {
                                "units": {
                                    "USD": [
                                        {
                                            "val": 900,
                                            "start": "2025-01-01",
                                            "end": "2025-03-31",
                                            "filed": "2025-05-02",
                                            "accn": "000-int",
                                            "form": "10-Q",
                                        }
                                    ]
                                }
                            }
                        }
                    }
                }
            ).encode(),
            200,
        )

    provider = SecEdgarProvider(
        user_agent="integration-test test@example.com",
        ticker_map={"TEST": "123"},
        transport=transport,
        retries=0,
    )
    period = Period(date(2025, 1, 1), date(2025, 3, 31), "quarter")
    observations = provider.metric_inputs(Ticker("TEST"), period, date(2025, 5, 3))
    path = tmp_path / "provider.db"
    with SQLiteStorage(path) as storage:
        storage.save_observation(Ticker("TEST"), observations[0])
        assert storage.load_observations(Ticker("TEST"), date(2025, 4, 30)) == ()
    with SQLiteStorage(path) as storage:
        visible = storage.load_observations(Ticker("TEST"), date(2025, 5, 3))
        assert visible[0].value == 900.0
        assert visible[0].provenance.filing_date == date(2025, 5, 2)
        derived = calculate_metric("revenue", [fact_from_observation(visible[0])], date(2025, 5, 3))
        assert derived.value == 900.0
        assert derived.source_provenance[0].raw_identifier == "0000000123/000-int/10-Q/revenue"
