# api/view.py
import json
from http.server import BaseHTTPRequestHandler

import requests

BWIBBU_URL = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_d"
STOCK_DAY_ALL_URL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"


def fetch_json(url: str):
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list):
        raise RuntimeError(f"unexpected upstream payload from {url}")
    return data


def normalize_bwibbu(item):
    return {
        "Code": str(item.get("Code", "")),
        "Name": item.get("Name", ""),
        "DividendYield(%)": item.get("DividendYield", ""),
        "PE": item.get("PEratio", ""),
        "PB": item.get("PBratio", ""),
        "FiscalYearQuarter": item.get("FiscalYearQuarter", ""),
    }


def normalize_stock_day(item):
    return {
        "Open": item.get("OpeningPrice", ""),
        "High": item.get("HighestPrice", ""),
        "Low": item.get("LowestPrice", ""),
        "Close": item.get("ClosingPrice", ""),
        "Change": item.get("Change", ""),
        "TradeVolume": item.get("TradeVolume", ""),
        "TradeValue": item.get("TradeValue", ""),
        "Transaction": item.get("Transaction", ""),
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            bwibbu = fetch_json(BWIBBU_URL)
            stock_day = fetch_json(STOCK_DAY_ALL_URL)

            stock_by_code = {
                str(item.get("Code", "")): normalize_stock_day(item)
                for item in stock_day
                if item.get("Code")
            }

            all_data = []
            for item in bwibbu:
                code = str(item.get("Code", ""))
                if not code:
                    continue
                merged = normalize_bwibbu(item)
                merged.update(stock_by_code.get(code, {}))
                all_data.append(merged)

            payload = {
                "ok": True,
                "all_data": all_data,
                "source": "TWSE_OPENAPI_DIRECT",
                "bwibbu_count": len(bwibbu),
                "stock_day_count": len(stock_day),
            }
            out = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("content-type", "application/json; charset=utf-8")
            self.send_header("cache-control", "public, s-maxage=300, stale-while-revalidate=300")
            self.end_headers()
            self.wfile.write(out)
        except Exception as e:
            out = json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False).encode("utf-8")
            self.send_response(502)
            self.send_header("content-type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(out)
