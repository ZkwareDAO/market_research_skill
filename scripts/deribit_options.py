#!/usr/bin/env python3
"""
Deribit 期权快照

获取 BTC/ETH 在 Deribit 上的期权数据：
- ATM 期权价格和隐含波动率 (IV)
- 25-Delta Call/Put 的 IV

到期日：本周五、下周五、月底
"""

import os
import sys
import time
import requests
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

DERIBIT_API_BASE = os.getenv("DERIBIT_API_BASE", "https://www.deribit.com/api/v2")
OUTPUT_PATH = Path(
    os.getenv("OUTPUT_PATH", Path(__file__).parent.parent / "output")
)
HTTPS_PROXY = os.getenv("HTTPS_PROXY", "")
CURRENCIES = ["BTC", "ETH"]


def _build_session() -> requests.Session:
    session = requests.Session()
    if HTTPS_PROXY:
        session.proxies = {"https": HTTPS_PROXY, "http": HTTPS_PROXY}
    session.timeout = 15
    return session


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TargetExpiry:
    label: str          # "本周五" / "下周五" / "月底"
    date_str: str       # "05-09"
    timestamp_ms: int   # Deribit expiration_timestamp (ms)


@dataclass(frozen=True)
class ATMData:
    currency: str
    expiry: TargetExpiry
    strike: float
    call_price: Optional[float]
    put_price: Optional[float]
    call_iv: Optional[float]
    put_iv: Optional[float]
    underlying_price: float


@dataclass(frozen=True)
class Delta25Data:
    currency: str
    expiry: TargetExpiry
    call_iv: Optional[float]
    call_strike: Optional[float]
    call_delta: Optional[float]
    put_iv: Optional[float]
    put_strike: Optional[float]
    put_delta: Optional[float]


# ---------------------------------------------------------------------------
# Deribit API client
# ---------------------------------------------------------------------------

class DeribitClient:
    def __init__(self, session: requests.Session) -> None:
        self._s = session
        self._base = DERIBIT_API_BASE

    def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{self._base}{path}"
        resp = self._s.get(url, params=params or {})
        resp.raise_for_status()
        body = resp.json()
        if "result" not in body:
            raise ValueError(f"Deribit API error: {body}")
        return body["result"]

    def get_instruments(self, currency: str) -> list[dict]:
        return self._get(
            "/public/get_instruments",
            {"currency": currency, "kind": "option", "expired": "false"},
        )

    def get_book_summary(self, currency: str) -> list[dict]:
        return self._get(
            "/public/get_book_summary_by_currency",
            {"currency": currency, "kind": "option"},
        )

    def get_ticker(self, instrument_name: str) -> dict:
        return self._get("/public/ticker", {"instrument_name": instrument_name})


# ---------------------------------------------------------------------------
# Expiry date helpers
# ---------------------------------------------------------------------------

def _next_weekday(dt: datetime, weekday: int) -> datetime:
    """Return the next date with the given weekday (0=Mon, 4=Fri)."""
    days_ahead = weekday - dt.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return dt + timedelta(days=days_ahead)


def _find_target_expiries(available_timestamps_ms: set[int]) -> list[TargetExpiry]:
    """Pick the 3 target expiries from the available Deribit expiry timestamps."""
    now_utc = datetime.now(timezone.utc)

    # Deribit settles at 08:00 UTC on expiry day
    settle_hour = 8

    # --- this Friday ---
    if now_utc.weekday() == 4 and now_utc.hour < settle_hour:
        this_friday = now_utc.date()
    elif now_utc.weekday() == 4 and now_utc.hour >= settle_hour:
        this_friday = (now_utc + timedelta(days=7)).date()
    else:
        this_friday = _next_weekday(now_utc, 4).date()

    next_friday = this_friday + timedelta(days=7)

    # --- end of month: last day of current month ---
    if now_utc.month == 12:
        month_end = now_utc.replace(year=now_utc.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        month_end = now_utc.replace(month=now_utc.month + 1, day=1) - timedelta(days=1)
    month_end = month_end.date()

    # Convert dates to 08:00 UTC timestamps (ms)
    def _to_ms(d):
        dt = datetime(d.year, d.month, d.day, settle_hour, 0, 0, tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)

    candidates = [
        ("本周五", this_friday, _to_ms(this_friday)),
        ("下周五", next_friday, _to_ms(next_friday)),
        ("月底", month_end, _to_ms(month_end)),
    ]

    results: list[TargetExpiry] = []
    for label, date_val, target_ms in candidates:
        if target_ms in available_timestamps_ms:
            results.append(TargetExpiry(
                label=label,
                date_str=date_val.strftime("%m-%d"),
                timestamp_ms=target_ms,
            ))
        else:
            # Find the closest available expiry within ±3 days
            closest = min(
                available_timestamps_ms,
                key=lambda t: abs(t - target_ms),
                default=None,
            )
            if closest and abs(closest - target_ms) < 3 * 86400 * 1000:
                closest_date = datetime.fromtimestamp(closest / 1000, tz=timezone.utc).date()
                results.append(TargetExpiry(
                    label=f"{label}(实际{closest_date.strftime('%m-%d')})",
                    date_str=closest_date.strftime("%m-%d"),
                    timestamp_ms=closest,
                ))
            else:
                print(f"  警告：未找到 {label} ({date_val}) 附近的到期日，跳过")

    return results


# ---------------------------------------------------------------------------
# Analysis logic
# ---------------------------------------------------------------------------

def _find_atm_options(
    currency: str,
    expiry: TargetExpiry,
    instruments: list[dict],
    summaries_by_name: dict[str, dict],
) -> ATMData | None:
    """Find ATM call and put for a given expiry."""
    # Filter instruments for this expiry
    expiry_instruments = [
        inst for inst in instruments
        if inst["expiration_timestamp"] == expiry.timestamp_ms
    ]
    if not expiry_instruments:
        return None

    # Get underlying price from any summary
    underlying_price = None
    for inst in expiry_instruments:
        summary = summaries_by_name.get(inst["instrument_name"])
        if summary and summary.get("underlying_price"):
            underlying_price = summary["underlying_price"]
            break
    if underlying_price is None:
        return None

    # Find ATM strike (closest to underlying price)
    strikes = sorted({inst["strike"] for inst in expiry_instruments})
    atm_strike = min(strikes, key=lambda s: abs(s - underlying_price))

    # Find ATM call and put
    call_name = None
    put_name = None
    for inst in expiry_instruments:
        if inst["strike"] == atm_strike:
            if inst["option_type"] == "call":
                call_name = inst["instrument_name"]
            else:
                put_name = inst["instrument_name"]

    call_summary = summaries_by_name.get(call_name, {}) if call_name else {}
    put_summary = summaries_by_name.get(put_name, {}) if put_name else {}

    return ATMData(
        currency=currency,
        expiry=expiry,
        strike=atm_strike,
        call_price=call_summary.get("mark_price"),
        put_price=put_summary.get("mark_price"),
        call_iv=call_summary.get("mark_iv"),
        put_iv=put_summary.get("mark_iv"),
        underlying_price=underlying_price,
    )


def _find_25delta_options(
    currency: str,
    expiry: TargetExpiry,
    instruments: list[dict],
    client: DeribitClient,
) -> Delta25Data | None:
    """Find 25-delta call and put for a given expiry by querying ticker API."""
    expiry_instruments = [
        inst for inst in instruments
        if inst["expiration_timestamp"] == expiry.timestamp_ms
    ]
    if not expiry_instruments:
        return None

    calls = [i for i in expiry_instruments if i["option_type"] == "call"]
    puts = [i for i in expiry_instruments if i["option_type"] == "put"]

    best_call: dict | None = None
    best_call_diff = float("inf")
    best_put: dict | None = None
    best_put_diff = float("inf")

    # Fetch delta for all calls
    for inst in calls:
        try:
            ticker = client.get_ticker(inst["instrument_name"])
            delta = ticker.get("greeks", {}).get("delta")
            if delta is None:
                continue
            diff = abs(delta - 0.25)
            if diff < best_call_diff:
                best_call_diff = diff
                best_call = {
                    "iv": ticker.get("mark_iv"),
                    "strike": inst["strike"],
                    "delta": delta,
                }
            time.sleep(0.05)
        except Exception as e:
            print(f"    ticker {inst['instrument_name']} 失败: {e}")

    # Fetch delta for all puts
    for inst in puts:
        try:
            ticker = client.get_ticker(inst["instrument_name"])
            delta = ticker.get("greeks", {}).get("delta")
            if delta is None:
                continue
            diff = abs(delta - (-0.25))
            if diff < best_put_diff:
                best_put_diff = diff
                best_put = {
                    "iv": ticker.get("mark_iv"),
                    "strike": inst["strike"],
                    "delta": delta,
                }
            time.sleep(0.05)
        except Exception as e:
            print(f"    ticker {inst['instrument_name']} 失败: {e}")

    return Delta25Data(
        currency=currency,
        expiry=expiry,
        call_iv=best_call["iv"] if best_call else None,
        call_strike=best_call["strike"] if best_call else None,
        call_delta=best_call["delta"] if best_call else None,
        put_iv=best_put["iv"] if best_put else None,
        put_strike=best_put["strike"] if best_put else None,
        put_delta=best_put["delta"] if best_put else None,
    )


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _fmt_iv(iv: float | None) -> str:
    if iv is None:
        return "N/A"
    return f"{iv:.1f}%"


def _fmt_price(price: float | None) -> str:
    if price is None:
        return "N/A"
    return f"{price:.4f}"


def generate_report(
    atm_results: dict[str, list[ATMData]],
    delta_results: dict[str, list[Delta25Data]],
) -> str:
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = [f"# Deribit 期权快照 ({now_str})", ""]

    # --- ATM section ---
    for currency in CURRENCIES:
        atm_list = atm_results.get(currency, [])
        if not atm_list:
            continue

        underlying = atm_list[0].underlying_price if atm_list else 0
        lines.append(f"## ATM 期权 — {currency} (现货: ${underlying:,.0f})")
        lines.append("")
        lines.append(
            "| 到期日 | 行权价 | Call 价格 | Put 价格 | Call IV | Put IV |"
        )
        lines.append("|--------|--------|-----------|----------|---------|--------|")

        for atm in atm_list:
            lines.append(
                f"| {atm.expiry.date_str} ({atm.expiry.label}) "
                f"| {atm.strike:,.0f} "
                f"| {_fmt_price(atm.call_price)} "
                f"| {_fmt_price(atm.put_price)} "
                f"| {_fmt_iv(atm.call_iv)} "
                f"| {_fmt_iv(atm.put_iv)} |"
            )
        lines.append("")

    # --- 25-Delta section ---
    lines.append("## 25-Delta IV")
    lines.append("")

    for currency in CURRENCIES:
        d25_list = delta_results.get(currency, [])
        if not d25_list:
            continue

        lines.append(f"### {currency}")
        lines.append("")
        lines.append(
            "| 到期日 | 25D Call IV | 25D Call Strike | 25D Put IV | 25D Put Strike | Risk Reversal |"
        )
        lines.append(
            "|--------|------------|-----------------|------------|----------------|---------------|"
        )

        for d25 in d25_list:
            rr = ""
            if d25.call_iv is not None and d25.put_iv is not None:
                rr = f"{d25.call_iv - d25.put_iv:+.1f}%"
            else:
                rr = "N/A"

            call_strike_str = f"{d25.call_strike:,.0f}" if d25.call_strike else "N/A"
            put_strike_str = f"{d25.put_strike:,.0f}" if d25.put_strike else "N/A"

            lines.append(
                f"| {d25.expiry.date_str} ({d25.expiry.label}) "
                f"| {_fmt_iv(d25.call_iv)} "
                f"| {call_strike_str} "
                f"| {_fmt_iv(d25.put_iv)} "
                f"| {put_strike_str} "
                f"| {rr} |"
            )
        lines.append("")

    lines.append(f"---\n*报告生成时间：{now_str}*\n")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run() -> str:
    session = _build_session()
    client = DeribitClient(session)

    atm_results: dict[str, list[ATMData]] = {}
    delta_results: dict[str, list[Delta25Data]] = {}

    for currency in CURRENCIES:
        print(f"\n=== {currency} ===")

        # Step 1: get instruments + book summary
        print(f"  获取 {currency} 期权合约列表...", end=" ")
        instruments = client.get_instruments(currency)
        print(f"{len(instruments)} 个合约")

        print(f"  获取 {currency} 期权摘要...", end=" ")
        summaries = client.get_book_summary(currency)
        summaries_by_name = {s["instrument_name"]: s for s in summaries}
        print(f"{len(summaries)} 条")

        # Step 2: find target expiries
        available_expiries = {inst["expiration_timestamp"] for inst in instruments}
        target_expiries = _find_target_expiries(available_expiries)
        print(f"  目标到期日：{[e.label for e in target_expiries]}")

        if not target_expiries:
            print(f"  未找到匹配的到期日，跳过 {currency}")
            continue

        # Step 3: ATM options
        atm_list: list[ATMData] = []
        for expiry in target_expiries:
            print(f"  查找 ATM ({expiry.label})...", end=" ")
            atm = _find_atm_options(currency, expiry, instruments, summaries_by_name)
            if atm:
                atm_list.append(atm)
                print(f"行权价 {atm.strike:,.0f}, IV={_fmt_iv(atm.call_iv)}/{_fmt_iv(atm.put_iv)}")
            else:
                print("未找到")
        atm_results[currency] = atm_list

        # Step 4: 25-delta options
        d25_list: list[Delta25Data] = []
        for expiry in target_expiries:
            print(f"  查找 25-Delta ({expiry.label})...", end=" ")
            d25 = _find_25delta_options(currency, expiry, instruments, client)
            if d25:
                d25_list.append(d25)
                print(f"Call IV={_fmt_iv(d25.call_iv)}, Put IV={_fmt_iv(d25.put_iv)}")
            else:
                print("未找到")
        delta_results[currency] = d25_list

    # Generate report
    report = generate_report(atm_results, delta_results)

    # Save to file
    output_dir = OUTPUT_PATH / "options_snapshot"
    output_dir.mkdir(parents=True, exist_ok=True)
    now_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
    file_path = output_dir / f"snapshot_{now_str}.md"
    file_path.write_text(report, encoding="utf-8")
    print(f"\n报告已保存：{file_path}")

    # Print to console
    print("\n" + "=" * 60)
    print(report)

    return report


def main() -> None:
    run()


if __name__ == "__main__":
    main()
