# api/push.py
import os, json, requests
from http.server import BaseHTTPRequestHandler
import gspread
from google.oauth2.service_account import Credentials
# (移除了 pandas 和 datetime，因為不再需要 T86)

BWIBBU_URL = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_d"
# (移除了 T86_URL)

def get_or_create_worksheet(sh, title):
    """
    通用函式：取得一個工作表，如果不存在就建立它
    """
    try:
        ws = sh.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=title, rows="100", cols="20")
    return ws

# (移除了 fetch_institutional_data 函式)

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
    爬取本益比資料 (使用修正後的正確欄位名稱)
    """
    r = requests.get(BWIBBU_URL, timeout=20)
    r.raise_for_status()
    data = r.json()  # list of dict
    
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

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            sh = get_sheet()
            
            # === 任務 1：更新 BWIBBU_d ===
            ws_bwibbu = get_or_create_worksheet(sh, "BWIBBU_d")
            rows_bwibbu = fetch_bwibbu()
            
            header = ["Code", "Name", "DividendYield(%)", "PE", "PB", "FiscalYearQuarter"]
            
            ws_bwibbu.clear()
            ws_bwibbu.append_row(header) # append_row 會自動處理格式
            if rows_bwibbu:
                ws_bwibbu.append_rows(rows_bwibbu, value_input_option="USER_ENTERED")

            # === (任務 2：三大法人已移除) ===
            
            # --- 修改：簡化回傳的 body ---
            body = {
                "ok": True, 
                "bwibbu_count": len(rows_bwibbu), 
                "sheets_updated": [ws_bwibbu.title]
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
