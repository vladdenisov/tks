import socket
import sys
import time
import json

class HeartbeatClient:
    def __init__(self, host, port, interval=1):
        self.host = host
        self.port = port
        self.interval = interval  # Интервал между heartbeat'ами в секундах
        self.sequence = 0
        
    def start(self):
        # Создаем UDP сокет
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        print(f'UDP Heartbeat клиент запущен')
        print(f'Отправка heartbeat на {self.host}:{self.port} каждые {self.interval} сек')
        
        try:
            while True:
                # Увеличиваем номер последовательности
                self.sequence += 1
                
                # Формируем heartbeat пакет
                heartbeat = {
                    'sequence': self.sequence,
                    'timestamp': time.time()
                }
                
                # Отправляем пакет
                try:
                    client_socket.sendto(json.dumps(heartbeat).encode(), (self.host, self.port))
                    print(f'Отправлен heartbeat #{self.sequence}')
                    
                except Exception as e:
                    print(f'Ошибка при отправке heartbeat: {e}')
                    
                # Ждем до следующего интервала
                time.sleep(self.interval)
                
        except KeyboardInterrupt:
            print("\nКлиент остановлен")
            client_socket.close()
            sys.exit(0)

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print('Использование: python udp_heartbeat_client.py хост порт')
        sys.exit(1)
        
    host = sys.argv[1]
    port = int(sys.argv[2])
    
    client = HeartbeatClient(host, port)
    client.start()