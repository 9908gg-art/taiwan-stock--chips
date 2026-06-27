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
