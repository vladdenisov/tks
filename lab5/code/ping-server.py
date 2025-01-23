import socket
import sys

def start_server(port):
    # Создаем UDP сокет
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # Привязываем сокет к адресу и порту
    server_socket.bind(('', port))
    print(f'UDP Пинг-сервер запущен на порту {port}')
    
    try:
        while True:
            # Получаем данные и адрес клиента
            message, client_address = server_socket.recvfrom(1024)
            
            # Просто отправляем данные обратно (эхо)
            server_socket.sendto(message, client_address)
            
    except KeyboardInterrupt:
        print("\nСервер остановлен")
        server_socket.close()
        sys.exit(0)

if __name__ == '__main__':
    port = 12000  # Порт по умолчанию
    if len(sys.argv) == 2:
        port = int(sys.argv[1])
    start_server(port)