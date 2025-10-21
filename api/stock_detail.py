import os, json, requests
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# API 來源：TWTAUU - 個股日成交資訊 (包含開高低收、成交量)
TWTAUU_URL = "https://openapi.twse.com.tw/v1/exchangeReport/TWTAUU"

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            # 1. 解析 URL 上的 ?code=... 參數
            query_components = parse_qs(urlparse(self.path).query)
            stock_code = query_components.get('code', [None])[0]

            if not stock_code:
                self.send_response(400)
                self.send_header("content-type", "application/json; charset=utf-8")
                self.end_headers()
                err_body = {"ok": False, "error": "請提供股票代碼 (code)"}
                self.wfile.write(json.dumps(err_body).encode("utf-8"))
                return

            # 2. 呼叫 TWSE OpenAPI
            # (注意：TWTAUU 必定是回傳 '所有' 上市公司資料，我們無法只查詢單一隻)
            r = requests.get(TWTAUU_URL, timeout=20)
            r.raise_for_status()
            data = r.json()

            # 3. 從 1000+ 筆資料中，找出我們要的那一筆
            found_stock = None
            for stock in data:
                if stock.get("Code") == stock_code:
                    found_stock = stock
                    break # 找到了，就跳出迴圈
            
            if found_stock:
                # 4. 成功找到，回傳這一筆資料
                payload = {"ok": True, "data": found_stock}
                self.send_response(200)
                self.send_header("content-type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(payload).encode("utf-8"))
            else:
                # 5. API 回傳了，但裡面沒有這支股票
                self.send_response(404)
                self.send_header("content-type", "application/json; charset=utf-8")
                self.end_headers()
                err_body = {"ok": False, "error": f"在 TWTAUU API 中找不到代碼 {stock_code}"}
                self.wfile.write(json.dumps(err_body).encode("utf-8"))

        except Exception as e:
            self.send_response(500)
            self.send_header("content-type", "application/json; charset=utf-8")
            self.end_headers()
            err_body = {"ok": False, "error": str(e)}
            self.wfile.write(json.dumps(err_body).encode("utf-8"))
