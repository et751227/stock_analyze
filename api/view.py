# api/view.py
import os, json
from http.server import BaseHTTPRequestHandler
import gspread
from google.oauth2.service_account import Credentials

def get_ws():
    """
    修改：只取得 "BWIBBU_d" 工作表
    """
    info = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(os.environ["SHEET_ID"])
    return sh.worksheet("BWIBBU_d")

# (移除了 read_institutional_data 函式)

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            # --- 修改：簡化讀取邏輯 ---
            ws = get_ws()
            values = ws.get_all_values()  # 2D array: [ [header...], [row1...], ... ]
            
            if not values or len(values) < 2:
                payload = {"ok": True, "bwibbu_data": []} # 回傳 bwibbu_data
            else:
                header = values[0]
                data = [dict(zip(header, r)) for r in values[1:]]
                payload = {"ok": True, "bwibbu_data": data} # 回傳 bwibbu_data
            
            out = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("content-type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(out)
            
        except Exception as e:
            out = json.dumps({"ok": False, "error": str(e)}).encode("utf-8")
            self.send_response(500)
            self.send_header("content-type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(out)
