# api/push.py
import os, json, requests
from http.server import BaseHTTPRequestHandler
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- API 網址 (保持不變) ---
BWIBBU_URL = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_d"
STOCK_DAY_ALL_URL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"

def get_or_create_worksheet(sh, title):
    try:
        ws = sh.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=title, rows="1000", cols="20")
    return ws

def get_sheet():
    creds_json = os.environ["GOOGLE_CREDENTIALS_JSON"]
    info = json.loads(creds_json)
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(os.environ["SHEET_ID"])
    return sh

def fetch_bwibbu():
    r = requests.get(BWIBBU_URL, timeout=20)
    r.raise_for_status()
    data = r.json()
    rows = []
    for it in data:
        rows.append([
            it.get("Code", ""), it.get("Name", ""),
            it.get("DividendYield", ""), it.get("PEratio", ""),
            it.get("PBratio", ""), it.get("FiscalYearQuarter", "")
        ])
    return rows

def fetch_stock_day_all():
    r = requests.get(STOCK_DAY_ALL_URL, timeout=20)
    r.raise_for_status()
    return r.json()

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            sh = get_sheet()
            today_str = datetime.now().strftime('%Y-%m-%d')
            
            rows_bwibbu = fetch_bwibbu()
            rows_stock_day = fetch_stock_day_all()
            
            updated_sheets = []

            # === 任務 1：更新「儀表板」 (保持不變) ===
            ws_bwibbu = get_or_create_worksheet(sh, "BWIBBU_d")
            header_bwibbu = ["Code", "Name", "DividendYield(%)", "PE", "PB", "FiscalYearQuarter"]
            ws_bwibbu.clear()
            ws_bwibbu.append_row(header_bwibbu)
            if rows_bwibbu:
                ws_bwibbu.append_rows(rows_bwibbu, value_input_option="USER_ENTERED")
            updated_sheets.append(ws_bwibbu.title)

            # === 任務 2：儲存「歷史資料 - BWIBBU」 (保持不變) ===
            ws_hist_bwibbu = get_or_create_worksheet(sh, "Historical_BWIBBU")
            if ws_hist_bwibbu.acell('A1').value is None:
                hist_header = ["QueryDate", "Code", "Name", "DividendYield(%)", "PE", "PB", "FiscalYearQuarter"]
                ws_hist_bwibbu.append_row(hist_header, value_input_option="USER_ENTERED")
            rows_to_append_bwibbu = []
            for row in rows_bwibbu:
                rows_to_append_bwibbu.append([today_str] + row)
            if rows_to_append_bwibbu:
                ws_hist_bwibbu.append_rows(rows_to_append_bwibbu, value_input_option="USER_ENTERED")
            updated_sheets.append(ws_hist_bwibbu.title)

            # ========== (修改處：任務 3) ==========
            ws_hist_stock = get_or_create_worksheet(sh, "Historical_STOCK_DAY_ALL")
            
            # 1. 標題 (我們希望在 Sheet 中看到的欄位名)
            hist_header = ["QueryDate", "Code", "Name", "Open", "High", "Low", "Close", "Change", "TradeVolume", "TradeValue", "Transaction"]
            
            # 2. JSON 來源的 Key (API 回傳的*真正*欄位名)
            source_keys = [
                "Code", "Name", 
                "OpeningPrice",     # <-- 修正
                "HighestPrice",     # <-- 修正
                "LowestPrice",      # <-- 修正
                "ClosingPrice",     # <-- 修正
                "Change", "TradeVolume", "TradeValue", "Transaction"
            ]
            
            if ws_hist_stock.acell('A1').value is None:
                ws_hist_stock.append_row(hist_header, value_input_option="USER_ENTERED")

            rows_to_append_stock = []
            for stock_dict in rows_stock_day:
                new_row = [today_str] # 加上 QueryDate
                for key in source_keys: # 遍歷*正確的* source_keys
                    new_row.append(stock_dict.get(key, "")) # 用正確的 key 去抓資料
                rows_to_append_stock.append(new_row)
            
            if rows_to_append_stock:
                ws_hist_stock.append_rows(rows_to_append_stock, value_input_option="USER_ENTERED")
            updated_sheets.append(ws_hist_stock.title)
            # ========== (修改結束) ==========

            # --- 回傳結果 (保持不變) ---
            body = {
                "ok": True, 
                "bwibbu_count": len(rows_bwibbu), 
                "stock_day_count": len(rows_stock_day),
                "sheets_updated": updated_sheets
            }
            out = json.dumps(body).encode("utf-8")
            self.send_response(200)
            self.send_header("content-type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(out)
            
        except Exception as e:
            err = {"ok": False, "error": str(e)}
            out = json.dumps(err).encode("utf-8")
            self.send_response(500)
            self.send_header("content-type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(out)
