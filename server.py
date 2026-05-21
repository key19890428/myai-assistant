import json
import os
import threading
import time
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.request

# ---------------- [텔레그램 연동 정보 설정 완료] ----------------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
# ----------------------------------------------------------------

DATA_FILE = "calendar_events.json"

# 데이터 창고 파일이 없으면 자동 생성
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({}, f)

# 텔레그램 메시지 발송 엔진
def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = json.dumps({"chat_id": TELEGRAM_CHAT_ID, "text": text}).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req) as response:
            pass
    except Exception as e:
        print(f"❌ 텔레그램 발송 오류: {e}")

# 24시간 백그라운드 알림 감시 스케줄러
def alarm_checker():
    print("🔔 [알림 스케줄러] 백그라운드 감시가 가동되었습니다.")
    sent_alarms = set() # 중복 발송 방지용 저장소
    
    while True:
        try:
            # Render 서버(해외) 시간을 대한민국 시간(UTC+9)으로 보정
            now = datetime.utcnow() + timedelta(hours=9)
            current_date = now.strftime("%Y-%m-%d")
            current_time = now.strftime("%H:%M")
            
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    events = json.load(f)
                
                # 내일 날짜 계산 (전날 알림 체크용)
                tomorrow_date = (now + timedelta(days=1)).strftime("%Y-%m-%d")
                
                # 1. 당일 알림 대상 확인
                if current_date in events:
                    for ev in events[current_date]:
                        if ev.get('alarm') == 'same_day' and ev.get('alarmTime') == current_time:
                            alarm_key = f"{current_date}_{ev['title']}_{current_time}"
                            if alarm_key not in sent_alarms:
                                msg = f"⏰ [당일 알림] 잠시 후 일정이 있습니다!\n\n📌 일정: {ev['title']}\n🕒 시간: {ev.get('time', '미지정')}\n📍 장소: {ev.get('location', '-')}\n📝 메모: {ev.get('memo', '-')}"
                                send_telegram_message(msg)
                                sent_alarms.add(alarm_key)
                                
                # 2. 전날 알림 대상 확인
                if tomorrow_date in events:
                    for ev in events[tomorrow_date]:
                        if ev.get('alarm') == 'day_before' and ev.get('alarmTime') == current_time:
                            alarm_key = f"{tomorrow_date}_{ev['title']}_{current_time}_before"
                            if alarm_key not in sent_alarms:
                                msg = f"📢 [전날 알림] 내일 예정된 일정이 있습니다!\n\n📌 일정: {ev['title']}\n🕒 시간: {ev.get('time', '미지정')}\n📍 장소: {ev.get('location', '-')}\n📝 메모: {ev.get('memo', '-')}"
                                send_telegram_message(msg)
                                sent_alarms.add(alarm_key)
            
            # 매일 새벽 4시에 발송 완료 기록 초기화
            if current_time == "04:00":
                sent_alarms.clear()
                
        except Exception as e:
            print(f"⚠️ 알림 체커 루프 오류: {e}")
            
        time.sleep(60) # 1분마다 반복 체크

class CloudCalendarServer(BaseHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        if self.path == "/get_events":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = f.read()
            self.wfile.write(data.encode("utf-8"))
            
        # Render 접속 시 화면(HTML)을 함께 서비스
        elif self.path == "/" or self.path == "/calendar":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            with open("calendar.html", "r", encoding="utf-8") as f:
                html = f.read()
            self.wfile.write(html.encode("utf-8"))

    def do_POST(self):
        if self.path == "/save_events":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            new_events = json.loads(post_data.decode('utf-8'))
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(new_events, f, ensure_ascii=False, indent=4)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Success")

def run():
    # Render 환경변수 포트를 따르며 기본값은 8000
    port = int(os.environ.get("PORT", 8000))
    server_address = ('', port)
    httpd = HTTPServer(server_address, CloudCalendarServer)
    print(f"▶ Render 파이썬 비서 서버가 {port}번 포트에서 가동을 시작합니다.")
    
    # 텔레그램 알림 체크용 백그라운드 쓰레드 가동
    t = threading.Thread(target=alarm_checker, daemon=True)
    t.start()
    
    httpd.serve_forever()

if __name__ == '__main__':
    run()