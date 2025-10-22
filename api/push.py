# api/push.py
import os, json, requests
from http.server import BaseHTTPRequestHandler
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- API 網址 ---
BWIBBU_URL = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_d"
STOCK_DAY_ALL_URL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"

def get_or_create_worksheet(sh, title):
    """取得或建立工作表"""
    try:
        ws = sh.worksheet(title)
    except gspread.WorksheetNotFound:
        # 建立新工作表時給予足夠行數
        ws = sh.add_worksheet(title=title, rows="1500", cols="20")
    return ws

def get_sheet():
    """取得 Google Sheet 主檔案"""
    creds_json = os.environ["GOOGLE_CREDENTIALS_JSON"]
    info = json.loads(creds_json)
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(os.environ["SHEET_ID"])
    return sh

def fetch_bwibbu():
    """爬取本益比/殖利率 (BWIBBU_d) 資料"""
    r = requests.get(BWIBBU_URL, timeout=30) # 稍微增加 timeout
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
    """爬取個股日成交資訊 (STOCK_DAY_ALL) 資料"""
    r = requests.get(STOCK_DAY_ALL_URL, timeout=30) # 稍微增加 timeout
    r.raise_for_status()
    return r.json() # 返回 list of dicts

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            sh = get_sheet()
            today_str = datetime.now().strftime('%Y-%m-%d')
            
            # --- 抓取兩份 API 資料 ---
            rows_bwibbu = fetch_bwibbu() # list of lists
            rows_stock_day = fetch_stock_day_all() # list of dicts
            
            updated_sheets = []

            # === 任務 1：儀表板 - BWIBBU_d (覆寫) ===
            ws_bwibbu = get_or_create_worksheet(sh, "BWIBBU_d")
            header_bwibbu = ["Code", "Name", "DividendYield(%)", "PE", "PB", "FiscalYearQuarter"]
            ws_bwibbu.clear()
            ws_bwibbu.append_row(header_bwibbu, value_input_option="USER_ENTERED")
            if rows_bwibbu:
                # 使用 update 寫入，速度可能比 append_rows 快一點
                ws_bwibbu.update('A2', rows_bwibbu, value_input_option="USER_ENTERED")
            updated_sheets.append(ws_bwibbu.title)

            # === 任務 2：歷史 - Historical_BWIBBU (附加) ===
            ws_hist_bwibbu = get_or_create_worksheet(sh, "Historical_BWIBBU")
            hist_header_bwibbu = ["QueryDate", "Code", "Name", "DividendYield(%)", "PE", "PB", "FiscalYearQuarter"]
            if ws_hist_bwibbu.acell('A1').value is None:
                ws_hist_bwibbu.append_row(hist_header_bwibbu, value_input_option="USER_ENTERED")
            rows_to_append_bwibbu = [[today_str] + row for row in rows_bwibbu]
            if rows_to_append_bwibbu:
                ws_hist_bwibbu.append_rows(rows_to_append_bwibbu, value_input_option="USER_ENTERED")
            updated_sheets.append(ws_hist_bwibbu.title)

            # === 任務 3：歷史 - Historical_STOCK_DAY_ALL (附加) ===
            ws_hist_stock = get_or_create_worksheet(sh, "Historical_STOCK_DAY_ALL")
            hist_header_stock = ["QueryDate", "Code", "Name", "Open", "High", "Low", "Close", "Change", "TradeVolume", "TradeValue", "Transaction"]
            # API 原始 Key (已確認正確)
            source_keys_stock = ["Code", "Name", "OpeningPrice", "HighestPrice", "LowestPrice", "ClosingPrice", "Change", "TradeVolume", "TradeValue", "Transaction"]
            if ws_hist_stock.acell('A1').value is None:
                ws_hist_stock.append_row(hist_header_stock, value_input_option="USER_ENTERED")
            rows_to_append_stock = []
            for stock_dict in rows_stock_day:
                new_row = [today_str] + [stock_dict.get(key, "") for key in source_keys_stock]
                rows_to_append_stock.append(new_row)
            if rows_to_append_stock:
                ws_hist_stock.append_rows(rows_to_append_stock, value_input_option="USER_ENTERED")
            updated_sheets.append(ws_hist_stock.title)

            # === 任務 4：儀表板 - STOCK_DAY_ALL_Dashboard (覆寫) ===
            ws_stock_dashboard = get_or_create_worksheet(sh, "STOCK_DAY_ALL_Dashboard")
            # 我們希望儀表板看到的欄位名 (同歷史記錄，但不含 QueryDate)
            dashboard_header = ["Code", "Name", "Open", "High", "Low", "Close", "Change", "TradeVolume", "TradeValue", "Transaction"]
            # API 原始 Key (同歷史記錄)
            source_keys_dashboard = source_keys_stock
            
            dashboard_data_to_write = [dashboard_header] # 加上標題列
            for stock_dict in rows_stock_day:
                new_row = [stock_dict.get(key, "") for key in source_keys_dashboard]
                dashboard_data_to_write.append(new_row)
                
            ws_stock_dashboard.clear()
            if dashboard_data_to_write:
                # 使用 update 寫入 ('A1' 會自動擴展範圍)
                ws_stock_dashboard.update('A1', dashboard_data_to_write, value_input_option="USER_ENTERED")
            updated_sheets.append(ws_stock_dashboard.title)

            # --- 回傳結果 ---
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
