"""一键启动器: 启动Streamlit + 打开浏览器 (已运行时不再重复打开)."""
import subprocess, sys, time, webbrowser, os, socket

PORT = 8501
HOST = "localhost"

app_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", "app.py")


def port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((HOST, port)) == 0


already_running = port_in_use(PORT)

if already_running:
    print(f"服务已在运行: http://{HOST}:{PORT}")
else:
    print(f"\n{'='*50}")
    print(f"  A股量化系统 v1.0")
    print(f"  启动中...")
    print(f"{'='*50}\n")

    subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", app_path,
         "--server.port", str(PORT), "--server.headless", "true",
         "--server.enableCORS", "false", "--server.enableXsrfProtection", "false"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(4)
    webbrowser.open(f"http://{HOST}:{PORT}")
    print(f"  浏览器已打开: http://{HOST}:{PORT}")

print(f"  关闭此窗口停止服务\n")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("  服务已停止")
