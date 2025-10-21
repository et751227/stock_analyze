# api/view.py
import os, json
from http.server import BaseHTTPRequestHandler
import gspread
from google.oauth2.service_account import Credentials

def get_sh():
    info = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(os.environ["SHEET_ID"])
    return sh

def read_bwibbu_data(sh):
    ws = sh.worksheet("BWIBBU_d")
    values = ws.get_all_values()
    if not values or len(values) < 2:
        return []
    
    header = values[0]
    data = [dict(zip(header, r)) for r in values[1:]]
    return data

# --- (從這裡開始修改) ---
def read_institutional_data(sh):
    """
    讀取三大法人買賣超資料
    (對應 push.py 的新寫入格式)
    """
    try:
        ws = sh.worksheet("三大法人買賣超")
        
        # 讀取資料日期 (A1)
        inst_date = ws.acell('A1').value
        
        # 讀取買超標題 (A4)
        buy_header = ws.get('A4:C4')[0]
        # 讀取買超資料 (A5:C14)
        buy_rows = ws.get('A5:C14')
        
        # 讀取賣超標題 (A17)
        sell_header = ws.get('A17:C17')[0]
        # 讀取賣超資料 (A18:C27)
        sell_rows = ws.get('A18:C27')
        
        buy_top10 = [dict(zip(buy_header, r)) for r in buy_rows]
        sell_top10 = [dict(zip(sell_header, r)) for r in sell_rows]
        
        return {"date": inst_date, "buy_top10": buy_top10, "sell_top10": sell_top10}
        
    except gspread.WorksheetNotFound:
        print("Worksheet '三大法人買賣超' not found.")
        return {"date": "分頁尚未建立", "buy_top10": [], "sell_top10": []}
    except Exception as e:
        print(f"Error reading institutional data: {e}")
        return {"date": f"讀取錯誤: {e}", "buy_top10": [], "sell_top10": []}
# --- (修改結束) ---

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            sh = get_sh()
            
            bwibbu_data = read_bwibbu_data(sh)
            institutional_data = read_institutional_data(sh)
            
            payload = {
                "ok": True,
                "bwibbu_data": bwibbu_data,
                "institutional_data": institutional_data
            }
            
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
