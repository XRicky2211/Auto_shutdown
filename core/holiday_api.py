# --------------------------------------------------------------------------
# 文件：core/holiday_api.py
# 用途：获取中国法定节假日数据（网络 API + 本地 JSON 缓存）
#       数据来源：timor.tech 节假日 API
# --------------------------------------------------------------------------

import json
import urllib.request
import urllib.error
from datetime import date

from core.config_manager import load_settings, save_settings

HOLIDAY_API_URL = "https://timor.tech/api/holiday/year/{}"
TIMEOUT = 5


def fetch_holiday_data(year: int) -> tuple:
    """获取指定年份的节假日数据和区间（一次网络请求同时返回两者）。

    返回 (dates_set, periods_list)，例如：
        dates_set   = {"2026-01-01", "2026-10-01", ...}
        periods_list = [{"name": "元旦", "start": "2026-01-01", "end": "2026-01-03"}, ...]
    """
    result = _fetch_from_api(year)
    if result is not None:
        holidays, periods = result
        _save_cache(year, holidays, periods)
        return holidays, periods
    return _load_cache(year)


def fetch_holidays(year: int) -> set:
    """获取指定年份的中国法定节假日日期集合（兼容旧接口）。"""
    holidays, _ = fetch_holiday_data(year)
    return holidays


def get_holiday_periods(year: int) -> list:
    """获取指定年份的节假日区间列表（兼容旧接口）。"""
    _, periods = fetch_holiday_data(year)
    return periods


def _fetch_from_api(year: int):
    """从 timor.tech API 获取某年节假日数据

    返回 (dates_set, periods_list) 或 None。
    """
    url = HOLIDAY_API_URL.format(year)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None

    if raw.get("code") != 0:
        return None

    entries = []
    for info in raw.get("holiday", {}).values():
        if isinstance(info, dict) and info.get("holiday") and isinstance(info.get("date"), str):
            try:
                d = date.fromisoformat(info["date"])
                entries.append((d, info.get("name", "")))
            except ValueError:
                continue

    if not entries:
        return None

    entries.sort()
    holidays = {d.isoformat() for d, _ in entries}

    periods = []
    for d, name in entries:
        if periods:
            prev_end = periods[-1]["end"]
            if (d - prev_end).days <= 1:
                periods[-1]["end"] = d
                continue
        periods.append({"name": name, "start": d, "end": d})

    for p in periods:
        p["start"] = p["start"].isoformat()
        p["end"] = p["end"].isoformat()

    return holidays, periods


def _load_cache(year: int):
    """从本地 JSON 缓存读取节假日数据

    返回 (dates_set, periods_list)。
    """
    cfg = load_settings()
    cache = cfg.get("holiday_cache")
    if isinstance(cache, dict) and cache.get("year") == year:
        dates = set(cache.get("dates", []))
        periods = cache.get("periods", [])
        return dates, periods
    return set(), []


def _save_cache(year: int, holidays: set, periods: list):
    """将节假日数据和区间写入本地 JSON 缓存"""
    save_settings(
        holiday_cache={
            "year": year,
            "dates": sorted(holidays),
            "periods": periods,
        }
    )
