import socket
import os
from datetime import datetime
from threading import Thread

class HTTPServer:
    def __init__(self, host='localhost', port=8080):
        self.host = host
        self.port = port
        
    def start(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(5)
        print(f'[*] Сервер запущен на {self.host}:{self.port}')
        
        while True:
            client_socket, addr = server_socket.accept()
            print(f'[*] Получено соединение от {addr[0]}:{addr[1]}')
            client_thread = Thread(target=self.handle_client, args=(client_socket,))
            client_thread.start()
            
    def handle_client(self, client_socket):
        request = client_socket.recv(1024).decode()
        
        try:
            # Парсим HTTP запрос
            headers = request.split('\n')
            filename = headers[0].split()[1]
            if filename == '/':
                filename = '/index.html'
                
            # Убираем начальный слэш
            filename = filename[1:]
            
            # Проверяем существование файла
            if os.path.exists(filename):
                with open(filename, 'rb') as f:
                    content = f.read()
                response = self.create_response(200, content)
            else:
                response = self.create_response(404)
                
        except Exception as e:
            print(f'[!] Ошибка: {e}')
            response = self.create_response(500)
            
        client_socket.send(response)
        client_socket.close()
        
    def create_response(self, status_code, content=None):
        status_messages = {
            200: 'OK',
            404: 'Not Found',
            500: 'Internal Server Error'
        }
        
        # Формируем заголовки
        headers = [
            f'HTTP/1.1 {status_code} {status_messages[status_code]}',
            f'Date: {datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")}',
            'Server: Python HTTP Server',
            'Connection: close'
        ]
        
        if content:
            headers.extend([
                f'Content-Length: {len(content)}',
                'Content-Type: text/html; charset=utf-8'
            ])
            response = '\r\n'.join(headers).encode() + b'\r\n\r\n' + content
        else:
            response = '\r\n'.join(headers).encode() + b'\r\n\r\n'
            
        return response

if __name__ == '__main__':
    server = HTTPServer()
    server.start()