# api/view.py
import os, json
from http.server import BaseHTTPRequestHandler
import gspread
from google.oauth2.service_account import Credentials

# --- 修改 ---
def get_sh():
    """
    修改：取得整個 Spreadsheet 物件 (sh)，而不是單一工作表
    """
    info = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(os.environ["SHEET_ID"])
    return sh

# --- 新增 ---
def read_bwibbu_data(sh):
    """
    讀取本益比資料 (您原本的邏輯)
    """
    ws = sh.worksheet("BWIBBU_d")
    values = ws.get_all_values()  # 2D array: [ [header...], [row1...], ... ]
    if not values or len(values) < 2:
        return []
    
    header = values[0]
    data = [dict(zip(header, r)) for r in values[1:]]
    return data

# --- 新增 ---
def read_institutional_data(sh):
    """
    讀取三大法人買賣超資料
    (此邏輯對應 push.py 寫入的格式)
    """
    try:
        ws = sh.worksheet("三大法人買賣超")
        
        # 讀取資料日期 (A1)
        inst_date = ws.acell('A1').value
        
        # 讀取買超 (A4:C13)
        buy_rows = ws.get('A4:C13')
        
        # 讀取賣超 (A17:C26)
        sell_rows = ws.get('A17:C26')
        
        # 我們知道 push.py 寫入的欄位
        header = ['證券代號', '證券名稱', '三大法人買賣超股數']
        
        buy_top10 = [dict(zip(header, r)) for r in buy_rows]
        sell_top10 = [dict(zip(header, r)) for r in sell_rows]
        
        return {"date": inst_date, "buy_top10": buy_top10, "sell_top10": sell_top10}
        
    except gspread.WorksheetNotFound:
        print("Worksheet '三大法人買賣超' not found.")
        return {"date": "分頁尚未建立", "buy_top10": [], "sell_top10": []}
    except Exception as e:
        print(f"Error reading institutional data: {e}")
        return {"date": f"讀取錯誤: {e}", "buy_top10": [], "sell_top10": []}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            # --- 修改：一次取得 sh，然後分開讀取 ---
            sh = get_sh()
            
            # 1. 讀取本益比資料
            bwibbu_data = read_bwibbu_data(sh)
            
            # 2. 讀取三大法人資料
            institutional_data = read_institutional_data(sh)
            
            # 3. 組合回傳
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
