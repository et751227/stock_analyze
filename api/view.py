# api/view.py
import os, json
from http.server import BaseHTTPRequestHandler
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd # <-- 需要 pandas 來合併資料

def get_sh():
    """取得 GSpread Sheet 主檔案"""
    info = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(os.environ["SHEET_ID"])
    return sh

def get_data_as_df(sh, worksheet_title):
    """從分頁讀取資料並轉為 DataFrame"""
    try:
        ws = sh.worksheet(worksheet_title)
        values = ws.get_all_values()
        if not values or len(values) < 2:
            print(f"工作表 {worksheet_title} 為空或只有標題列。")
            return pd.DataFrame()
        
        header = values[0]
        data = values[1:]
        df = pd.DataFrame(data, columns=header)
        # 確保 Code 是字串，避免 merge 出錯
        if 'Code' in df.columns:
            df['Code'] = df['Code'].astype(str)
        return df
    except gspread.WorksheetNotFound:
        print(f"找不到工作表: {worksheet_title}")
        return pd.DataFrame()
    except Exception as e:
        print(f"讀取工作表 {worksheet_title} 時發生錯誤: {e}")
        return pd.DataFrame()

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            sh = get_sh()
            
            # 1. 讀取兩份儀表板資料
            df_bwibbu = get_data_as_df(sh, "BWIBBU_d")
            df_stock_day = get_data_as_df(sh, "STOCK_DAY_ALL_Dashboard")

            if df_bwibbu.empty or df_stock_day.empty:
                err_msg = "儀表板資料不完整 (BWIBBU_d 或 STOCK_DAY_ALL_Dashboard 是空的或讀取失敗)"
                print(err_msg)
                # 即使失敗，仍嘗試回傳至少一份資料
                if not df_bwibbu.empty:
                    data_list = df_bwibbu.fillna('').to_dict('records')
                    payload = {"ok": True, "all_data": data_list, "warning": "STOCK_DAY_ALL 資料缺失"}
                elif not df_stock_day.empty:
                    data_list = df_stock_day.fillna('').to_dict('records')
                    payload = {"ok": True, "all_data": data_list, "warning": "BWIBBU 資料缺失"}
                else:
                     raise Exception(err_msg) # 兩份都失敗才拋出錯誤
            else:
                # 2. 合併資料 (使用 'Code' 作為 key)
                #    (移除 stock_day 的 Name 以免衝突)
                if 'Name' in df_stock_day.columns:
                    df_stock_day = df_stock_day.drop(columns=['Name']) 
                
                df_merged = pd.merge(
                    df_bwibbu,
                    df_stock_day,
                    on="Code",
                    how="left" # 以 BWIBBU_d 為主表
                )

                # 3. 轉換回 JSON
                data_list = df_merged.fillna('').to_dict('records')
                payload = {"ok": True, "all_data": data_list}

            out = json.dumps(payload).encode("utf-8")
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
