import socket
import sys
import os
import threading
from urllib.parse import urlparse
import time
import json
from http.client import responses
import hashlib
import logging
import datetime

def setup_logging():
    """Configure logging settings"""
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"proxy_{timestamp}.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger('proxy_server')

class CacheManager:
    def __init__(self, cache_dir="cache"):
        self.cache_dir = cache_dir
        self.cache_index = {}
        self.cache_lock = threading.Lock()
        self.logger = logging.getLogger('proxy_server')
        
        # Создаем директорию для кэша, если её нет
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
            self.logger.info(f"Created cache directory: {cache_dir}")
            
        # Загружаем индекс кэша из файла
        self.load_cache_index()
    
    def load_cache_index(self):
        index_file = os.path.join(self.cache_dir, "cache_index.json")
        if os.path.exists(index_file):
            with open(index_file, 'r') as f:
                self.cache_index = json.load(f)
            self.logger.info(f"Loaded cache index with {len(self.cache_index)} entries")
    
    def save_cache_index(self):
        index_file = os.path.join(self.cache_dir, "cache_index.json")
        with open(index_file, 'w') as f:
            json.dump(self.cache_index, f)
    
    def get_cache_path(self, url):
        """Генерирует путь к кэшированному файлу"""
        hash_name = hashlib.md5(url.encode()).hexdigest()
        return os.path.join(self.cache_dir, hash_name)
    
    def is_cached(self, url):
        """Проверяет наличие URL в кэше"""
        with self.cache_lock:
            if url in self.cache_index:
                cache_path = self.get_cache_path(url)
                if os.path.exists(cache_path):
                    # Проверяем актуальность кэша (24 часа)
                    cache_time = self.cache_index[url]['time']
                    if time.time() - cache_time < 86400:  # 24 часа
                        self.logger.debug(f"Cache hit for URL: {url}")
                        return True
                    else:
                        # Удаляем устаревший кэш
                        os.remove(cache_path)
                        del self.cache_index[url]
                        self.save_cache_index()
                        self.logger.info(f"Removed expired cache for URL: {url}")
            return False
    
    def get_from_cache(self, url):
        """Получает данные из кэша"""
        if self.is_cached(url):
            cache_path = self.get_cache_path(url)
            with open(cache_path, 'rb') as f:
                return f.read()
        return None
    
    def save_to_cache(self, url, data, headers):
        """Сохраняет данные в кэш"""
        with self.cache_lock:
            cache_path = self.get_cache_path(url)
            with open(cache_path, 'wb') as f:
                f.write(data)
            
            self.cache_index[url] = {
                'time': time.time(),
                'headers': headers
            }
            self.save_cache_index()
            self.logger.info(f"Cached response for URL: {url}")

class ProxyServer:
    def __init__(self, host='', port=8888, cache_dir='cache'):
        self.host = host
        self.port = port
        self.logger = logging.getLogger('proxy_server')
        self.cache_manager = CacheManager(cache_dir)
        
    def start(self):
        """Запускает прокси-сервер"""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(5)
        
        self.logger.info(f'Proxy server started on {self.host}:{self.port}')
        
        while True:
            try:
                client_socket, client_address = server_socket.accept()
                self.logger.info(f'Accepted connection from {client_address}')
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket,)
                )
                client_thread.start()
            except KeyboardInterrupt:
                self.logger.info("Server shutdown initiated")
                break
            except Exception as e:
                self.logger.error(f"Error accepting connection: {e}", exc_info=True)
        
        server_socket.close()
        self.logger.info("Server stopped")
    
    def handle_client(self, client_socket):
        """Обрабатывает запрос клиента"""
        client_address = client_socket.getpeername()
        try:
            # Получаем запрос
            request = self.receive_request(client_socket)
            if not request:
                return
            
            # Парсим запрос
            method, url, headers, body = self.parse_request(request)
            self.logger.info(f"Received {method} request for {url} from {client_address}")
            
            # Проверяем кэш для GET-запросов
            if method == "GET" and self.cache_manager.is_cached(url):
                self.logger.info(f"Serving from cache: {url}")
                cached_data = self.cache_manager.get_from_cache(url)
                client_socket.send(cached_data)
                return
            
            # Отправляем запрос на целевой сервер
            response = self.forward_request(method, url, headers, body)
            if response:
                # Кэшируем GET-запросы
                if method == "GET":
                    self.cache_manager.save_to_cache(url, response, headers)
                
                # Отправляем ответ клиенту
                client_socket.send(response)
                self.logger.info(f"Sent response to {client_address} for {url}")
            
        except Exception as e:
            self.logger.error(f"Error handling request from {client_address}: {e}", exc_info=True)
            self.send_error(client_socket, 500)
        finally:
            client_socket.close()
            self.logger.debug(f"Closed connection from {client_address}")
    
    def receive_request(self, client_socket):
        """Получает HTTP-запрос от клиента"""
        request = b''
        client_socket.settimeout(5)

        try:
            while True:
                chunk = client_socket.recv(4096)
                if not chunk:
                    break
                request += chunk
                if b'\r\n\r\n' in request:
                    # Проверяем наличие тела запроса
                    header_end = request.index(b'\r\n\r\n') + 4
                    headers = request[:header_end].decode('utf-8', 'ignore')
                    content_length = 0
                    for line in headers.split('\r\n'):
                        if line.lower().startswith('content-length:'):
                            content_length = int(line.split(':')[1].strip())
                    
                    if content_length > 0:
                        while len(request) < header_end + content_length:
                            chunk = client_socket.recv(4096)
                            if not chunk:
                                break
                            request += chunk
                    break
                    
        except socket.timeout:
            print("Таймаут при получении запроса")
            return None
        
        return request
    
    def parse_request(self, request):
        """Парсит HTTP-запрос"""
        try:
            # Разделяем заголовки и тело
            headers_end = request.index(b'\r\n\r\n')
            headers_data = request[:headers_end].decode('utf-8')
            body = request[headers_end + 4:]
            
            # Парсим строку запроса
            request_lines = headers_data.split('\r\n')
            method, path, _ = request_lines[0].split(' ')
            
            # Парсим URL
            if not path.startswith('http'):
                path = 'http:/' + path
            
            # Парсим заголовки
            headers = {}
            for line in request_lines[1:]:
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers[key.strip()] = value.strip()

            print(f'method: {method}, path: {path}, headers: {headers}, body: {body}')
            
            return method, path, headers, body
            
        except Exception as e:
            print(f"Ошибка при парсинге запроса: {e}")
            raise
    
    def forward_request(self, method, url, headers, body):
        """Пересылает запрос на целевой сервер"""
        try:
            parsed_url = urlparse(url)
            host = parsed_url.netloc
            port = parsed_url.port or 80
            path = parsed_url.path or '/'
            if parsed_url.query:
                path += '?' + parsed_url.query
            
            self.logger.debug(f"Forwarding request to {host}:{port}{path}")
            
            # Создаем соединение
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10)
            s.connect((host, port))
            
            # Формируем запрос
            request = f"{method} {path} HTTP/1.1\r\n"
            request += f"Host: {host}\r\n"
            
            # Добавляем остальные заголовки
            for key, value in headers.items():
                if key.lower() not in ['host', 'proxy-connection']:
                    request += f"{key}: {value}\r\n"
            
            request += "Connection: close\r\n\r\n"
            
            # Отправляем запрос
            s.send(request.encode())
            
            # Отправляем тело запроса для POST
            if method == "POST" and body:
                s.send(body)
            
            # Получаем ответ
            response = b''
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                response += chunk
            
            s.close()
            return response
            
        except Exception as e:
            self.logger.error(f"Error forwarding request to {url}: {e}", exc_info=True)
            return None
    
    def send_error(self, client_socket, error_code):
        """Отправляет сообщение об ошибке клиенту"""
        error_message = responses.get(error_code, "Unknown Error")
        response = f"HTTP/1.1 {error_code} {error_message}\r\n"
        response += "Content-Type: text/html\r\n"
        response += "Connection: close\r\n"
        response += f"\r\n"
        response += f"<html><body><h1>{error_code} {error_message}</h1></body></html>"
        
        try:
            client_socket.send(response.encode())
        except:
            pass

if __name__ == "__main__":
    logger = setup_logging()
    
    if len(sys.argv) > 1:
        host = sys.argv[1]
    else:
        host = ''
    
    proxy = ProxyServer(host=host)
    proxy.start()