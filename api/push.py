# api/push.py
import os, json, requests
from http.server import BaseHTTPRequestHandler
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import pandas as pd

# (不再需要 gspread_dataframe)

BWIBBU_URL = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_d"  # 個股日本益比/殖利率/股價淨值比
T86_URL = "https://www.twse.com.tw/exchangeReport/T86?response=json&selectType=ALLBUT0999&date="

def get_or_create_worksheet(sh, title):
    """
    通用函式：取得一個工作表，如果不存在就建立它
    """
    try:
        ws = sh.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=title, rows="100", cols="20")
    return ws

def fetch_institutional_data():
    """
    爬取證交所三大法人買賣超資料並找出前10名
    """
    today = datetime.now()
    date_str = today.strftime('%Y%m%d')
    url = T86_URL + date_str
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        data = response.json()
        
        if data['stat'] != 'OK':
            # 如果今天沒資料 (例如假日或盤中)，嘗試抓前一天
            yesterday = today - timedelta(days=1)
            date_str = yesterday.strftime('%Y%m%d')
            url = T86_URL + date_str
            response = requests.get(url, headers=headers, timeout=20)
            data = response.json()
            if data['stat'] != 'OK':
                print(f"查詢 {date_str} 資料失敗: {data.get('message', '無資料')}")
                return None, None, None

    except Exception as e:
        print(f"爬取三大法人資料時發生錯誤: {e}")
        return None, None, None

    # 處理資料 (使用 pandas)
    df = pd.DataFrame(data['data'], columns=data['fields'])
    
    # 資料清理
    df_net = df[['證券代號', '證券名稱', '三大法人買賣超股數']].copy()
    
    # 轉換 '三大法人買賣超股數' 為數字
    df_net['三大法人買賣超股數'] = df_net['三大法人買賣超股數'].str.replace(',', '').astype(int)
    
    # 找出前 10 名
    df_buy_top10 = df_net.sort_values(by='三大法人買賣超股數', ascending=False).head(10).reset_index(drop=True)
    df_sell_top10 = df_net.sort_values(by='三大法人買賣超股數', ascending=True).head(10).reset_index(drop=True)
    
    return df_buy_top10, df_sell_top10, date_str


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
    爬取本益比資料
    """
    r = requests.get(BWIBBU_URL, timeout=20)
    r.raise_for_status()
    data = r.json()
    rows = []
    for it in data:
        rows.append([
            it.get("Code", ""),
            it.get("Name", ""),
            it.get("Yield", ""),
            it.get("PEratio", ""),
            it.get("PBratio", ""),
            it.get("Date", "")
        ])
    return rows

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            sh = get_sheet()
            
            # === 任務 1：更新 BWIBBU_d (您原本的邏輯，使用 append_row) ===
            ws_bwibbu = get_or_create_worksheet(sh, "BWIBBU_d")
            rows_bwibbu = fetch_bwibbu()
            header = ["Code", "Name", "Yield(%)", "PE", "PB", "Date"]
            ws_bwibbu.clear()
            ws_bwibbu.append_row(header) # append_row 函式會自動處理格式
            if rows_bwibbu:
                ws_bwibbu.append_rows(rows_bwibbu, value_input_option="USER_ENTERED")

            # === 任務 2：更新三大法人買賣超 (使用 update) ===
            ws_inst = get_or_create_worksheet(sh, "三大法人買賣超")
            df_buy, df_sell, data_date = fetch_institutional_data()
            
            ws_inst.clear()
            if df_buy is not None and df_sell is not None:
                
                # --- (這裡是修復 [400] 錯誤的關鍵) ---
                
                # 1. 寫入資料日期 (手動包裝成 list[list])
                ws_inst.update('A1', [[f"資料日期: {data_date}"]], value_input_option="USER_ENTERED")
                
                # 2. 將 DataFrame 轉換為 list (包含 header)
                header_list = df_buy.columns.values.tolist()
                buy_values = df_buy.values.tolist()
                sell_values = df_sell.values.tolist()
                
                # 加上標題列
                buy_data_to_write = [header_list] + buy_values
                sell_data_to_write = [header_list] + sell_values
                
                # 3. 寫入買超 (手動包裝 list[list])
                ws_inst.update('A3', [["== 買超前10名 =="]], value_input_option="USER_ENTERED")
                if buy_data_to_write:
                    # 'buy_data_to_write' 已經是 list[list]，不需修改
                    ws_inst.update('A4', buy_data_to_write, value_input_option="USER_ENTERED") 
                
                # 4. 寫入賣超 (手動包裝 list[list])
                ws_inst.update('A16', [["== 賣超前10名 =="]], value_input_option="USER_ENTERED")
                if sell_data_to_write:
                    # 'sell_data_to_write' 已經是 list[list]，不需修改
                    ws_inst.update('A17', sell_data_to_write, value_input_option="USER_ENTERED")
            
            else:
                # 查無資料時也用 list[list] 格式寫入
                ws_inst.update('A1', [["今日查無資料"]], value_input_option="USER_ENTERED")
            
            # --- (修復結束) ---

            body = {
                "ok": True, 
                "bwibbu_count": len(rows_bwibbu), 
                "institutional_date": data_date,
                "sheets_updated": [ws_bwibbu.title, ws_inst.title]
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
