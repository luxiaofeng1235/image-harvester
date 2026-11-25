#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Python 代理网关服务 (Proxy Gateway)
功能：自动按需提取、缓存、轮询、重试国内代理IP，支持 HTTP/HTTPS 隧道、精简监控日志及命令行参数配置。
启动命令示例：
  python3 proxy_gateway.py
  python3 proxy_gateway.py --port 8888
  python3 proxy_gateway.py -h
"""

import http.server
import socketserver
import threading
import time
import requests
import urllib.parse
import sys
import signal
import socket
import select
import argparse
from datetime import datetime

# ==================== 默认配置常量 ====================
DEFAULT_API_URL = "https://api.wandouapp.com/?app_key=e890aa7191c00cd2f641060591c4f1d0&num=1&xy=3&type=2&lb=\r\n&nr=0&area_id=&isp=0&"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 9999
DEFAULT_MAX_RETRIES = 2  # 单个请求最多尝试次数（每次失败会换一个新IP，即最多消耗的IP数）
# 全局变量，供运行时使用
API_URL = DEFAULT_API_URL

# ==================== 运行统计（线程安全） ====================
class ProxyStats:
    """记录请求数、成功/失败次数、平均耗时、累计提取IP数。

    耗时口径（仅统计成功请求）：
      - HTTP : 从开始转发到响应完整写回客户端（含重试）
      - HTTPS: 从收到 CONNECT 到隧道建立完成（不含隧道存活时间）
    """
    def __init__(self):
        self.lock = threading.Lock()
        self.counters = {
            "http": {"success": 0, "fail": 0, "elapsed": 0.0},
            "https": {"success": 0, "fail": 0, "elapsed": 0.0},
        }
        self.ip_fetched_total = 0

    def record_request(self, kind, success, elapsed=0.0):
        with self.lock:
            c = self.counters[kind]
            if success:
                c["success"] += 1
                c["elapsed"] += elapsed
            else:
                c["fail"] += 1

    def record_ip_fetch(self):
        """记录一次成功提取，返回当前累计数"""
        with self.lock:
            self.ip_fetched_total += 1
            return self.ip_fetched_total

    def summary(self, with_fetched=True):
        """返回单行统计摘要。with_fetched=False 时不含累计提取IP（该数字在每次取IP时单独输出）"""
        with self.lock:
            success = sum(c["success"] for c in self.counters.values())
            fail = sum(c["fail"] for c in self.counters.values())
            fetched = self.ip_fetched_total
            avg = {
                kind: (f"{c['elapsed'] / c['success']:.2f}s" if c["success"] else "-")
                for kind, c in self.counters.items()
            }
        text = (f"请求: 共{success + fail} 成功{success} 失败{fail} | "
                f"平均耗时: HTTP {avg['http']}, HTTPS建链 {avg['https']}")
        if with_fetched:
            text += f" | 累计提取IP: {fetched}个"
        return text


# ==================== 代理管理器（核心缓存与状态控制） ====================
class ProxyManager:
    def __init__(self, api_url, stats):
        self.api_url = api_url
        self.stats = stats
        self.lock = threading.Lock()
        self.current_ip = None
        self.current_port = None
        self.city = None
        self.isp = None
        self.expire_time = None

    def is_valid(self):
        """检查当前IP是否存在且未过期"""
        if not self.current_ip or not self.expire_time:
            return False
        return datetime.now() < self.expire_time

    def fetch_new_ip(self):
        """调用第三方API获取新的代理IP（带内部API请求重试与城市运营商解析）"""
        with self.lock:
            # 双重检查：防止并发时重复调用API（其他线程可能已换好IP）
            if self.is_valid():
                return True

            max_api_retries = 3
            for api_attempt in range(1, max_api_retries + 1):
                try:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [*] 正在从供应商API获取新代理IP (API尝试 {api_attempt}/{max_api_retries})...")
                    response = requests.get(self.api_url, timeout=10)
                    try:
                        data = response.json()
                    except ValueError:
                        # 非JSON返回（如HTML错误页）：构造成同样结构，走下面统一的失败提示
                        data = {"code": f"HTTP {response.status_code}",
                                "msg": f"返回内容不是JSON: {response.text[:200]!r}"}

                    if response.status_code != 200:
                        code = data.get("code", f"HTTP {response.status_code}")
                        msg = data.get("msg") or data.get("message") or "(API未返回msg字段)"
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [-] 获取IP失败: HTTP状态码={response.status_code} | code={code} | msg={msg} | 原始返回: {data}")
                    elif data.get("code") == 200 and data.get("data"):
                        item = data["data"][0]
                        # 每次成功从供应商取到IP都计入累计（含首次）
                        expire_str = item["expire_time"]
                        try:
                            expire_time = datetime.strptime(expire_str, "%Y-%m-%d %H:%M:%S")
                        except (TypeError, ValueError) as e:
                            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [-] 获取IP失败: expire_time格式无效 ({expire_str!r}) | 错误: {e} | 原始返回: {data}")
                        else:
                            fetched_total = self.stats.record_ip_fetch()
                            self.current_ip = item["ip"]
                            self.current_port = item["port"]
                            self.city = item.get("city", "未知")
                            self.isp = item.get("isp", "未知")
                            self.expire_time = expire_time

                            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [+] 成功获取新代理IP: {self.current_ip}:{self.current_port} | 城市: {self.city} | 运营商: {self.isp} | 过期时间: {self.expire_time} | 累计提取IP: {fetched_total}个")
                            return True
                    else:
                        code = data.get("code")
                        msg = data.get("msg") or data.get("message") or "(API未返回msg字段)"
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [-] 获取IP失败: code={code} | msg={msg} | 原始返回: {data}")
                except Exception as e:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [-] 获取IP请求网络异常 (API尝试 {api_attempt}): {e}")
                
                if api_attempt < max_api_retries:
                    time.sleep(1)
            
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 连续 {max_api_retries} 次调用代理提取API均失败。")
            return False

    def get_valid_ip(self):
        """获取可用IP：未过期则直接返回，过期或无效则重新获取"""
        with self.lock:
            if self.is_valid():
                return self.current_ip, self.current_port
        
        if self.fetch_new_ip():
            return self.current_ip, self.current_port
        return None, None

    def invalidate_current_ip(self):
        """强制使当前IP失效（用于请求失败时触发换IP）"""
        with self.lock:
            self.expire_time = datetime.now()


# ==================== HTTP 代理网关处理器 ====================
class ProxyHandler(http.server.BaseHTTPRequestHandler):
    proxy_manager = None
    max_retries = DEFAULT_MAX_RETRIES  # 由 main() 按命令行参数覆盖

    def do_CONNECT(self):
        """专门处理 HTTPS 请求的 CONNECT 隧道建立，并显式打印目标域名"""
        target_host_port = self.path
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [请求捕获] 客户端 {self.client_address[0]} -> HTTPS 目标: https://{target_host_port}")

        stats = self.proxy_manager.stats
        start_time = time.time()
        max_retries = self.max_retries
        attempt = 0

        while attempt < max_retries:
            ip, port = self.proxy_manager.get_valid_ip()
            if not ip or not port:
                stats.record_request("https", False)
                self.send_error(503, "Gateway Error: Failed to obtain proxy IP.")
                return

            upstream_sock = None
            tunnel_established = False
            try:
                upstream_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                upstream_sock.settimeout(15)
                upstream_sock.connect((ip, int(port)))

                connect_req = f"CONNECT {target_host_port} HTTP/1.1\r\nHost: {target_host_port}\r\n\r\n"
                upstream_sock.sendall(connect_req.encode('utf-8'))

                response = upstream_sock.recv(4096)
                status = self._parse_status_code(response)

                if status is not None and 400 <= status < 500:
                    # 上游代理是活的，只是拒绝了这个目标（如 407/403）。
                    # IP 本身没问题，换IP大概率同样被拒，所以不换IP、不重试，避免白白消耗付费IP。
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [警告] 上游代理 {ip}:{port} 拒绝了 {target_host_port} (状态码 {status})，IP 仍有效，不换IP")
                    stats.record_request("https", False)
                    try:
                        self.send_error(502, f"Gateway Error: upstream proxy rejected CONNECT with status {status}")
                    except OSError:
                        pass  # 客户端已断开，不能因此误判为代理故障而换IP
                    return

                if status is None or not (200 <= status < 300):
                    # 无响应 / 无法解析 / 5xx 等：视为代理节点本身故障，走下面的换IP重试
                    raise Exception(f"Upstream proxy bad CONNECT response: {response[:100]!r}")

                self.wfile.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                tunnel_established = True
                stats.record_request("https", True, time.time() - start_time)
                self._relay_traffic(self.connection, upstream_sock)
                return

            except Exception as e:
                if tunnel_established:
                    # 已向客户端返回 200，转发阶段出错不能再重试/换IP
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [警告] HTTPS隧道转发中断 {ip}:{port}: {e}")
                    return
                attempt += 1
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [警告] HTTPS隧道代理 {ip}:{port} 建立失败 (隧道尝试 {attempt}/{max_retries}): {e}")
                self.proxy_manager.invalidate_current_ip()
                if attempt >= max_retries:
                    stats.record_request("https", False)
                    self.send_error(502, f"Gateway Error: HTTPS tunnel failed after {max_retries} retries.")
                    return

            finally:
                # 无论成功、失败还是重试，都确保上游 socket 被释放
                if upstream_sock is not None:
                    try:
                        upstream_sock.close()
                    except OSError:
                        pass

    @staticmethod
    def _parse_status_code(raw):
        """从上游代理响应的状态行解析状态码（如 b'HTTP/1.1 407 OK'），解析失败返回 None"""
        try:
            return int(raw.split(b"\r\n", 1)[0].split(b" ", 2)[1])
        except (IndexError, ValueError):
            return None

    def _relay_traffic(self, client_sock, upstream_sock):
        """底层 TCP 流量双向转发（用于 HTTPS 隧道）"""
        client_sock.setblocking(False)
        upstream_sock.setblocking(False)
        sockets = [client_sock, upstream_sock]
        timeout = 60

        while True:
            try:
                readable, _, _ = select.select(sockets, [], [], timeout)
                if not readable:
                    break
                for sock in readable:
                    other = upstream_sock if sock is client_sock else client_sock
                    data = sock.recv(8192)
                    if not data:
                        return
                    other.sendall(data)
            except Exception as e:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [警告] HTTPS隧道流量转发中断: {e}")
                break

    def do_request(self, method):
        """统一处理所有普通 HTTP 请求的转发与重试逻辑，并打印完整 URL"""
        parsed_url = urllib.parse.urlparse(self.path)
        if not parsed_url.scheme:
            host_header = self.headers.get("Host", "")
            target_url = f"http://{host_header}{self.path}"
        else:
            target_url = self.path

        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [请求捕获] 客户端 {self.client_address[0]} -> HTTP [{method}] 目标URL: {target_url}")

        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else None

        headers = {}
        excluded_headers = ['host', 'connection', 'proxy-connection', 'content-length']
        for key, value in self.headers.items():
            if key.lower() not in excluded_headers:
                headers[key] = value

        stats = self.proxy_manager.stats
        start_time = time.time()
        max_retries = self.max_retries
        attempt = 0

        while attempt < max_retries:
            ip, port = self.proxy_manager.get_valid_ip()
            if not ip or not port:
                stats.record_request("http", False)
                self.send_error(503, "Gateway Error: Failed to obtain proxy IP.")
                return

            proxies = {
                "http": f"http://{ip}:{port}",
                "https": f"http://{ip}:{port}"
            }

            try:
                resp = requests.request(
                    method=method,
                    url=target_url,
                    headers=headers,
                    data=body,
                    proxies=proxies,
                    allow_redirects=False,
                    timeout=15
                )

                self.send_response(resp.status_code)
                for k, v in resp.headers.items():
                    if k.lower() not in ['content-encoding', 'transfer-encoding', 'connection']:
                        self.send_header(k, v)
                self.end_headers()
                self.wfile.write(resp.content)
                stats.record_request("http", True, time.time() - start_time)
                return

            except Exception as e:
                attempt += 1
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [警告] 代理 {ip}:{port} 请求失败 (请求尝试 {attempt}/{max_retries}): {e}")
                self.proxy_manager.invalidate_current_ip()

                if attempt >= max_retries:
                    stats.record_request("http", False)
                    self.send_error(502, f"Gateway Error: Request failed after {max_retries} retries.")
                    return

    def do_GET(self): self.do_request("GET")
    def do_POST(self): self.do_request("POST")
    def do_PUT(self): self.do_request("PUT")
    def do_DELETE(self): self.do_request("DELETE")
    def do_HEAD(self): self.do_request("HEAD")

    def log_message(self, format, *args):
        pass


# ==================== 监控线程 ====================
def monitor_ip_status(proxy_mgr):
    """每隔10秒在 CLI 打印精简后的当前IP、剩余有效时间与请求统计"""
    while True:
        time.sleep(10)
        with proxy_mgr.lock:
            if proxy_mgr.current_ip and proxy_mgr.expire_time:
                remaining = proxy_mgr.expire_time - datetime.now()
                total_seconds = int(remaining.total_seconds())
                if total_seconds > 0:
                    mins = total_seconds // 60
                    secs = total_seconds % 60
                    print(f"[监控状态] 代理IP: {proxy_mgr.current_ip}:{proxy_mgr.current_port} | 剩余时间: {mins}分 {secs}秒")
                else:
                    pass
            else:
                pass
        # 在持有 proxy_mgr.lock 之外读取统计，避免嵌套加锁
        print(f"[统计] {proxy_mgr.stats.summary(with_fetched=False)}")


# ==================== 多线程服务器支持 ====================
class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="Python 本地动态代理网关服务，支持 HTTP/HTTPS 隧道转发与自动轮换。")
    parser.add_argument("--host", type=str, default=DEFAULT_HOST, help=f"监听的主机地址 (默认: {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"监听的端口号 (默认: {DEFAULT_PORT})")
    parser.add_argument("--api", type=str, default=DEFAULT_API_URL, help="上游代理 IP 提取 API 链接")
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES,
                        help=f"单个请求最多尝试次数，每次失败会换一个新IP，即单请求最多消耗的IP数 (默认: {DEFAULT_MAX_RETRIES})")
    args = parser.parse_args()
    if args.max_retries < 1:
        parser.error("--max-retries 必须 >= 1")

    start_time = time.time()

    stats = ProxyStats()
    proxy_mgr = ProxyManager(args.api, stats)
    ProxyHandler.proxy_manager = proxy_mgr
    ProxyHandler.max_retries = args.max_retries

    server = ThreadedHTTPServer((args.host, args.port), ProxyHandler)
    print("=" * 60)
    print(f"[初始化成功] 代理网关服务已启动")
    print(f"[监听地址]   http://{args.host}:{args.port}")
    print(f"[重试策略]   单请求最多尝试 {args.max_retries} 次（失败即换IP，最多消耗 {args.max_retries} 个IP）")
    print(f"[操作提示]   按 Ctrl+C 可以安全优雅地退出程序。")
    print(f"[帮助说明]   运行 python3 {sys.argv[0]} -h 可查看完整参数选项。")
    print("=" * 60)

    monitor_thread = threading.Thread(target=monitor_ip_status, args=(proxy_mgr,), daemon=True)
    monitor_thread.start()

    def signal_handler(sig, frame):
        elapsed_seconds = time.time() - start_time
        elapsed_minutes = elapsed_seconds / 60.0

        print("\n" + "=" * 60)
        print("[关闭中] 收到终止信号，正在安全关闭网关服务...")
        server.server_close()
        print(f"[统计信息] 服务总运行时间: {elapsed_minutes:.2f} 分钟")
        print(f"[统计信息] {stats.summary()}")
        print("[已退出] 服务已成功退出，欢迎下次使用！")
        print("=" * 60)
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        server.serve_forever()
    except Exception as e:
        pass


if __name__ == "__main__":
    main()
