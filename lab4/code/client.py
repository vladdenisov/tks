import socket
import sys

def send_request(host, port, filename):
    try:
        # Создаем TCP соединение
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((host, int(port)))
        
        # Формируем HTTP запрос
        request = f'GET /{filename} HTTP/1.1\r\nHost: {host}\r\n\r\n'
        
        # Отправляем запрос
        client_socket.send(request.encode())
        
        # Получаем ответ
        response = b''
        while True:
            data = client_socket.recv(1024)
            if not data:
                break
            response += data
            
        # Закрываем соединение
        client_socket.close()
        
        # Декодируем и выводим ответ
        print(response.decode('utf-8', errors='ignore'))
        
    except Exception as e:
        print(f'Ошибка: {e}')
        sys.exit(1)

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print('Использование: python client.py хост порт имя_файла')
        sys.exit(1)
        
    host = sys.argv[1]
    port = sys.argv[2]
    filename = sys.argv[3]
    
    send_request(host, port, filename)