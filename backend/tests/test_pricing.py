from decimal import Decimal

import pytest

from workly.domain.errors import ValidationFailed
from workly.domain.orders import check_description, is_night
from workly.domain.pricing import Duration, PriceConfig, PriceUnit, QuoteInput, calculate

DAY_150 = PriceConfig.from_base(PriceUnit.DAY, 150_000)


def test_min_max_defaults():
    assert (DAY_150.min_price, DAY_150.max_price) == (112_500, 300_000)  # TZ 8-jadval
    cfg = PriceConfig.from_base(PriceUnit.DAY, 130_000)
    assert (cfg.min_price, cfg.max_price) == (97_500, 260_000)


def test_tz_example_with_commission():
    # TZ 8-bo'lim: 3 ta umumiy ishchi, 1 kun — 450 000 + 10% = 495 000; ishchi 145 500 oladi
    q = calculate(DAY_150, QuoteInput(workers=3, duration=Duration.DAY), commission_enabled=True)
    assert (q.subtotal, q.service_fee, q.employer_total, q.worker_net) == (450_000, 45_000, 495_000, 145_500)
    assert q.platform_income == 45_000 + 4_500 * 3  # TZ 9: 19 500 bitta ishchidan


def test_pilot_no_commission():
    q = calculate(DAY_150, QuoteInput(workers=3, duration=Duration.DAY), commission_enabled=False)
    assert (q.service_fee, q.employer_total, q.worker_net, q.platform_income) == (0, 450_000, 150_000, 0)


def test_half_day_and_surcharges():
    q = calculate(DAY_150, QuoteInput(workers=1, duration=Duration.HALF_DAY), commission_enabled=False)
    assert q.worker_price == 90_000  # ×0.6
    q = calculate(
        DAY_150,
        QuoteInput(workers=1, duration=Duration.DAY, worker_tools=True, top_only=True),
        commission_enabled=False,
    )
    assert q.worker_price == 180_000  # +10% +10%


def test_multi_day():
    q = calculate(DAY_150, QuoteInput(workers=2, duration=Duration.MULTI_DAY, days=3), commission_enabled=False)
    assert (q.days, q.subtotal) == (3, 900_000)
    with pytest.raises(ValidationFailed):
        calculate(DAY_150, QuoteInput(workers=2, duration=Duration.MULTI_DAY, days=1), commission_enabled=False)


def test_volume_unit_min_order_and_split():
    cfg = PriceConfig.from_base(PriceUnit.M2, 5_000, min_order_amount=200_000)
    q = calculate(cfg, QuoteInput(workers=2, volume=Decimal(30)), commission_enabled=False)
    assert q.subtotal == 200_000 and q.worker_price == 100_000  # 150 000 < eng kam summa
    q = calculate(cfg, QuoteInput(workers=3, volume=Decimal(100)), commission_enabled=False)
    assert q.worker_price == 167_000 and q.subtotal == 501_000  # 500 000 / 3, 1 000 ga yaxlit
    with pytest.raises(ValidationFailed):
        calculate(cfg, QuoteInput(workers=1), commission_enabled=False)


def test_day_unit_requires_duration():
    with pytest.raises(ValidationFailed):
        calculate(DAY_150, QuoteInput(workers=1), commission_enabled=False)


@pytest.mark.parametrize(
    "hhmm,night", [("22:00", True), ("23:30", True), ("05:59", True), ("06:00", False), ("21:59", False)]
)
def test_night(hhmm, night):
    from datetime import time

    assert is_night(time.fromisoformat(hhmm)) is night


@pytest.mark.parametrize(
    "text", ["Qarz undirish kerak", "qo'riqchi kerak", "Нужен коллектор", "intim xizmat", "pasportingizni qoldirasiz"]
)
def test_prohibited(text):
    with pytest.raises(ValidationFailed):
        check_description(text)


@pytest.mark.parametrize("text", ["Uyni ko'chirish, mebel tashish", "Долго работать не нужно", None, ""])
def test_allowed(text):
    check_description(text)
