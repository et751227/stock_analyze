import os, json, requests
from http.server import BaseHTTPRequestHandler
import gspread
from google.oauth2.service_account import Credentials

BWIBBU_URL = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_d"  # 個股日本益比/殖利率/股價淨值比

def get_sheet():
    creds_json = os.environ["GOOGLE_CREDENTIALS_JSON"]
    info = json.loads(creds_json)
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(os.environ["SHEET_ID"])
    # 使用固定工作表名稱；不存在就建立
    try:
        ws = sh.worksheet("BWIBBU_d")
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title="BWIBBU_d", rows="1", cols="10")
    return ws

def fetch_bwibbu():
    r = requests.get(BWIBBU_URL, timeout=20)
    r.raise_for_status()
    data = r.json()  # list of dict
    # 欄位：Code, Name, Yield, PEratio, PBratio, Date
    rows = []
    for it in data:
        rows.append([
            it.get("Code", ""),
            it.get("Name", ""),
            it.get("Yield", ""),     # 殖利率（%）
            it.get("PEratio", ""),   # 本益比
            it.get("PBratio", ""),   # 股價淨值比
            it.get("Date", "")       # 資料日期
        ])
    return rows

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            ws = get_sheet()
            # 取資料
            rows = fetch_bwibbu()
            # 改成字串、去逗號等清理（可依需求加強）
            header = ["Code", "Name", "Yield(%)", "PE", "PB", "Date"]
            ws.clear()
            ws.append_row(header)
            if rows:
                ws.append_rows(rows, value_input_option="USER_ENTERED")

            body = {"ok": True, "count": len(rows), "sheet": ws.title}
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
