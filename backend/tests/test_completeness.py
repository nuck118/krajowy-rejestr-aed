from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.services.completeness import completeness_tier, compute_completeness_score
from app.services.opening_hours import is_open_now


def test_completeness_full_score() -> None:
    now = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
    score = compute_completeness_score(
        latitude=53.1235,
        longitude=18.0084,
        location_description="Main entrance hall, left wall next to security desk",
        street_address="ul. Jezuicka 1",
        city="Bydgoszcz",
        postal_code="85-102",
        teryt_code="0461011",
        access_type="public",
        opening_hours="24/7",
        is_24_7=True,
        indoor=True,
        status="operational",
        last_verified_at=now - timedelta(days=30),
        now=now,
    )
    assert score == 100
    assert completeness_tier(score) == "Standard Compliant"


def test_completeness_minimal_and_stale() -> None:
    now = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
    score = compute_completeness_score(
        latitude=52.2297,
        longitude=21.0122,
        location_description="Hol",  # 3 chars -> 5 pts
        street_address=None,
        city=None,
        postal_code=None,
        teryt_code=None,
        access_type="public",  # 5 pts
        opening_hours=None,
        is_24_7=False,
        indoor=None,
        status="unverified",
        last_verified_at=now - timedelta(days=400),  # > 365 days -> 0 pts
        now=now,
    )
    assert score == 30
    assert completeness_tier(score) == "Incomplete"


def test_completeness_minimum_harvestable_threshold() -> None:
    now = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
    score = compute_completeness_score(
        latitude=52.2297,
        longitude=21.0122,
        location_description="Przy wejściu głównym po prawej stronie",
        street_address="ul. Marszałkowska 10",
        city="Warszawa",
        postal_code=None,
        teryt_code=None,
        access_type="public",
        opening_hours=None,
        is_24_7=False,
        indoor=None,
        status="unverified",
        last_verified_at=None,
        now=now,
    )
    assert score == 70
    assert completeness_tier(score) == "Minimum Harvestable"


def test_opening_hours_warsaw_evaluation() -> None:
    warsaw_tz = ZoneInfo("Europe/Warsaw")
    # Friday 10:00
    fri_morning = datetime(2026, 11, 20, 10, 0, tzinfo=warsaw_tz)
    # Saturday 10:00
    sat_morning = datetime(2026, 11, 21, 10, 0, tzinfo=warsaw_tz)
    # Friday 23:30
    fri_late = datetime(2026, 11, 20, 23, 30, tzinfo=warsaw_tz)

    assert is_open_now("24/7", is_24_7=True, now=sat_morning) is True
    assert is_open_now("Mo-Fr 07:30-15:30; Sa-Su, PH off", now=fri_morning) is True
    assert is_open_now("Mo-Fr 07:30-15:30; Sa-Su, PH off", now=sat_morning) is False
    assert is_open_now("Mo-Su 05:00-00:30", now=fri_late) is True
    assert is_open_now(None, is_24_7=False, now=fri_morning) is None
