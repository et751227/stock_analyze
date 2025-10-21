# api/push.py
import os, json, requests
from http.server import BaseHTTPRequestHandler
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime # <-- 匯入 datetime

# --- API 網址 ---
# 1. PE/PB/殖利率 (您目前在用的)
BWIBBU_URL = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_d"
# 2. 開高低收/成交量 (您在個股查詢用的)
STOCK_DAY_ALL_URL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"

def get_or_create_worksheet(sh, title):
    """
    通用函式：取得一個工作表，如果不存在就建立它
    """
    try:
        ws = sh.worksheet(title)
    except gspread.WorksheetNotFound:
        # 建立新工作表，預設 1000 行
        ws = sh.add_worksheet(title=title, rows="1000", cols="20")
    return ws

def get_sheet():
    """
    取得 Google Sheet 主檔案 (sh)
    """
    creds_json = os.environ["GOOGLE_CREDENTIALS_JSON"]
    info = json.loads(creds_json)
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(os.environ["SHEET_ID"])
    return sh

def fetch_bwibbu():
    """
    爬取本益比/殖利率 (BWIBBU_d) 資料
    """
    r = requests.get(BWIBBU_URL, timeout=20)
    r.raise_for_status()
    data = r.json()  # list of dict
    
    # 轉換為 list of lists
    rows = []
    for it in data:
        rows.append([
            it.get("Code", ""),
            it.get("Name", ""),
            it.get("DividendYield", ""),  # 殖利率
            it.get("PEratio", ""),       # 本益比
            it.get("PBratio", ""),       # 股價淨值比
            it.get("FiscalYearQuarter", "") # 資料季度
        ])
    return rows

def fetch_stock_day_all():
    """
    (新函式) 爬取個股日成交資訊 (STOCK_DAY_ALL) 資料
    """
    r = requests.get(STOCK_DAY_ALL_URL, timeout=20)
    r.raise_for_status()
    return r.json()  # 返回 list of dicts

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            sh = get_sheet()
            
            # 這是歷史資料的關鍵：我們要標記這些資料是「哪一天」抓的
            today_str = datetime.now().strftime('%Y-%m-%d')
            
            # --- 抓取兩份 API 資料 ---
            rows_bwibbu = fetch_bwibbu() # 這是 list of lists
            rows_stock_day = fetch_stock_day_all() # 這是 list of dicts
            
            updated_sheets = []

            # === 任務 1：更新「儀表板」 (您現在的邏輯，保持不變) ===
            ws_bwibbu = get_or_create_worksheet(sh, "BWIBBU_d")
            header_bwibbu = ["Code", "Name", "DividendYield(%)", "PE", "PB", "FiscalYearQuarter"]
            ws_bwibbu.clear()
            ws_bwibbu.append_row(header_bwibbu)
            if rows_bwibbu:
                ws_bwibbu.append_rows(rows_bwibbu, value_input_option="USER_ENTERED")
            updated_sheets.append(ws_bwibbu.title)

            # === 任務 2：(新功能) 儲存「歷史資料 - BWIBBU」 ===
            ws_hist_bwibbu = get_or_create_worksheet(sh, "Historical_BWIBBU")
            
            # 如果是第一次寫入 (A1 是空的)，就先寫入標題
            if ws_hist_bwibbu.acell('A1').value is None:
                hist_header = ["QueryDate", "Code", "Name", "DividendYield(%)", "PE", "PB", "FiscalYearQuarter"]
                ws_hist_bwibbu.append_row(hist_header, value_input_option="USER_ENTERED")

            # 準備要附加的資料：在每一筆資料前加上「查詢日期」
            rows_to_append_bwibbu = []
            for row in rows_bwibbu:
                new_row = [today_str] + row # row 本身就是 list
                rows_to_append_bwibbu.append(new_row)
            
            # (最重要) 使用 append_rows **附加**資料，絕不清除！
            if rows_to_append_bwibbu:
                ws_hist_bwibbu.append_rows(rows_to_append_bwibbu, value_input_option="USER_ENTERED")
            updated_sheets.append(ws_hist_bwibbu.title)


            # === 任務 3：(新功能) 儲存「歷史資料 - STOCK_DAY_ALL」 ===
            ws_hist_stock = get_or_create_worksheet(sh, "Historical_STOCK_DAY_ALL")
            
            # 定義我們要儲存的欄位順序
            stock_day_keys = ["Code", "Name", "Open", "High", "Low", "Close", "Change", "TradeVolume", "TradeValue", "Transaction"]
            
            # 如果是第一次寫入 (A1 是空的)，就先寫入標題
            if ws_hist_stock.acell('A1').value is None:
                hist_header = ["QueryDate"] + stock_day_keys
                ws_hist_stock.append_row(hist_header, value_input_option="USER_ENTERED")

            # 準備要附加的資料：
            rows_to_append_stock = []
            for stock_dict in rows_stock_day: # 這是 list of dicts
                new_row = [today_str]
                for key in stock_day_keys:
                    new_row.append(stock_dict.get(key, ""))
                rows_to_append_stock.append(new_row)
            
            # (最重要) 使用 append_rows **附加**資料，絕不清除！
            if rows_to_append_stock:
                ws_hist_stock.append_rows(rows_to_append_stock, value_input_option="USER_ENTERED")
            updated_sheets.append(ws_hist_stock.title)


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
