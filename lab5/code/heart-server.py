import socket
import sys
import time
import json
from datetime import datetime


class HeartbeatServer:
  def __init__(self, port, timeout=10):
    self.port = port
    self.timeout = timeout  # Таймаут в секундах
    self.clients = {}  # Словарь для хранения информации о клиентах

  def start(self):
    # Создаем UDP сокет
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind(('', self.port))

    print(f'UDP Heartbeat сервер запущен на порту {self.port}')
    print(f'Таймаут для клиентов: {self.timeout} секунд')

    try:
      while True:
        # Получаем данные и адрес клиента
        try:
          data, client_address = server_socket.recvfrom(1024)
          current_time = time.time()

          # Парсим полученные данные
          try:
              heartbeat_data = json.loads(data.decode())
              sequence = heartbeat_data['sequence']
              timestamp = heartbeat_data['timestamp']

              # Вычисляем RTT
              rtt = (current_time - timestamp) * 1000  # в миллисекундах

              # Обновляем информацию о клиенте
              if client_address not in self.clients:
                  self.clients[client_address] = {
                      'last_sequence': sequence,
                      'last_seen': current_time,
                      'packets_received': 1,
                      'min_rtt': rtt,
                      'max_rtt': rtt,
                      'total_rtt': rtt
                  }
              else:
                  client = self.clients[client_address]
                  expected_sequence = client['last_sequence'] + 1

                  if sequence != expected_sequence:
                      lost_packets = sequence - expected_sequence
                      print(f'Потеряно пакетов 
от {client_address}: {lost_packets}')
                      
                  client['last_sequence'] = sequence
                  client['last_seen'] = current_time
                  client['packets_received'] += 1
                  client['min_rtt'] = min(client['min_rtt'], rtt)
                  client['max_rtt'] = max(client['max_rtt'], rtt)
                  client['total_rtt'] += rtt
                  
              print(f'Получен heartbeat от {client_address}, seq={sequence}, 
RTT={rtt:.2f}ms')
              
          except json.JSONDecodeError:
              print(f'Получены некорректные данные от {client_address}')
                
        except socket.timeout:
            pass
            
        # Проверяем таймауты клиентов
        current_time = time.time()
        for addr, client in list(self.clients.items()):
            if current_time - client['last_seen'] > self.timeout:
                print(f'Клиент {addr} отключился (таймаут)')
                print(f'Статистика клиента:')
                print(f'Получено пакетов: {client["packets_received"]}')
                print(f'RTT min/avg/max = '
                      f'{client["min_rtt"]:.2f}/'
                      f'{(client["total_rtt"]/client["packets_received"]):.2f}/'
                      f'{client["max_rtt"]:.2f} ms')
                del self.clients[addr]
                
        time.sleep(0.1)  # Небольшая задержка для снижения нагрузки на CPU
          
    except KeyboardInterrupt:
        print("\nСервер остановлен")
        server_socket.close()
        sys.exit(0)

if __name__ == '__main__':
  port = 12000  # Порт по умолчанию
  if len(sys.argv) == 2:
      port = int(sys.argv[1])
  
  server = HeartbeatServer(port)
  server.start()