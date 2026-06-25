import http.server
import socketserver
import threading
import time
import sys
import os
import json
import webbrowser
from crawler_daemon import run_crawl

PORT = 8000
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_GET(self):
        # 1. API: Get subscribers list
        if self.path == '/api/subscribers':
            sub_file = os.path.join(DIRECTORY, "data", "subscribers.json")
            subscribers = {"emails": [], "telegram_chat_ids": []}
            if os.path.exists(sub_file):
                try:
                    with open(sub_file, "r", encoding="utf-8") as f:
                        subscribers = json.load(f)
                except:
                    pass
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
            self.end_headers()
            self.wfile.write(json.dumps(subscribers, ensure_ascii=False).encode('utf-8'))
        else:
            super().do_GET()

    def do_POST(self):
        # 2. API: Add subscriber
        if self.path == '/api/subscribe':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            try:
                params = json.loads(post_data)
                sub_type = params.get('type') # 'email' or 'telegram'
                value = params.get('value', '').strip()
                
                if not value:
                    self.send_error_response(400, "訂閱地址或 ID 不能為空")
                    return
                
                # Check email format if email
                if sub_type == 'email' and not re.match(r'[^@]+@[^@]+\.[^@]+', value):
                    # We can use a simple regex for basic check
                    self.send_error_response(400, "信箱格式不正確")
                    return
                
                data_dir = os.path.join(DIRECTORY, "data")
                os.makedirs(data_dir, exist_ok=True)
                sub_file = os.path.join(data_dir, "subscribers.json")
                
                subscribers = {"emails": [], "telegram_chat_ids": []}
                if os.path.exists(sub_file):
                    try:
                        with open(sub_file, "r", encoding="utf-8") as f:
                            subscribers = json.load(f)
                    except:
                        pass
                
                # Append if not duplicate
                if sub_type == 'email':
                    if value not in subscribers["emails"]:
                        subscribers["emails"].append(value)
                elif sub_type == 'telegram':
                    if value not in subscribers["telegram_chat_ids"]:
                        subscribers["telegram_chat_ids"].append(value)
                else:
                    self.send_error_response(400, "無效的訂閱類別")
                    return
                    
                with open(sub_file, "w", encoding="utf-8") as f:
                    json.dump(subscribers, f, indent=2, ensure_ascii=False)
                
                # Async git push to store subscriber back to GitHub
                def git_push_subscribers():
                    import subprocess
                    try:
                        # Add, commit and push to remote origin
                        res_add = subprocess.run(["git", "add", sub_file], capture_output=True, text=True)
                        if res_add.returncode != 0:
                            print("[Git] Add failed:", res_add.stderr)
                            return
                        res_commit = subprocess.run(["git", "commit", "-m", "chore(subscribers): new subscription"], capture_output=True, text=True)
                        res_push = subprocess.run(["git", "push"], capture_output=True, text=True)
                        if res_push.returncode != 0:
                            print("[Git] Push failed:", res_push.stderr)
                            print("[Git] Tip: If authentication failed, please check your Git credentials or SSH configuration.")
                        else:
                            print("[Git] Successfully pushed subscribers list back to GitHub.")
                    except Exception as ge:
                        print("[Git] Failed to push subscription back to GitHub:", ge)
                
                threading.Thread(target=git_push_subscribers, daemon=True).start()
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success", "message": "訂閱成功！已儲存並推送到 GitHub。"}).encode('utf-8'))
                
            except Exception as e:
                self.send_error_response(500, f"伺服器錯誤: {str(e)}")
        else:
            self.send_response(404)
            self.end_headers()
            
    def send_error_response(self, code, msg):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"status": "error", "message": msg}).encode('utf-8'))

# Inline re import for email matching
import re

def start_server():
    socketserver.TCPServer.allow_reuse_address = True
    while True:
        try:
            with socketserver.TCPServer(("", PORT), Handler) as httpd:
                print(f"\n[Dashboard Server] Running locally at: http://localhost:{PORT}")
                print(f"[Dashboard Server] Serving files from: {DIRECTORY}")
                print("[Dashboard Server] Press Ctrl+C in this terminal to exit.")
                
                def open_browser():
                    time.sleep(1.5)
                    print(f"[Dashboard Server] Opening browser to http://localhost:{PORT} ...")
                    webbrowser.open(f"http://localhost:{PORT}")
                
                threading.Thread(target=open_browser, daemon=True).start()
                httpd.serve_forever()
        except OSError as e:
            global PORT
            if e.errno == 98 or e.errno == 48:
                print(f"[Dashboard Server] Port {PORT} is occupied. Trying next port...")
                PORT += 1
            else:
                print(f"[Dashboard Server] Server failed to start: {e}")
                break

def start_crawler_loop():
    print("[Crawler Daemon] Starting background news crawler thread...")
    while True:
        try:
            run_crawl()
        except Exception as e:
            print(f"[Crawler Daemon] Crawl error in background: {e}")
        time.sleep(60)

def main():
    os.chdir(DIRECTORY)
    print("[Launcher] Performing initial data synchronization...")
    try:
        run_crawl()
    except Exception as e:
        print(f"[Launcher] Initial sync failed: {e}")

    crawler_thread = threading.Thread(target=start_crawler_loop, daemon=True)
    crawler_thread.start()

    try:
        start_server()
    except KeyboardInterrupt:
        print("\n[Launcher] Shutting down server. Goodbye!")
        sys.exit(0)

if __name__ == "__main__":
    main()
