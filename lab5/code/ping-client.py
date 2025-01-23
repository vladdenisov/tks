import socket
import time
import sys
import statistics

def ping(host, port, count=4):
    # Создаем UDP сокет
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # Устанавливаем таймаут в 1 секунду
    client_socket.settimeout(1.0)
    
    # Статистика
    rtts = []
    packets_sent = 0
    packets_received = 0
    
    print(f'PING {host}:{port}')
    
    try:
        for i in range(count):
            # Формируем сообщение с номером пакета
            message = f'Ping {i + 1}'.encode()
            
            start_time = time.time()
            packets_sent += 1
            
            try:
                # Отправляем сообщение
                client_socket.sendto(message, (host, port))
                
                # Получаем ответ
                data, server = client_socket.recvfrom(1024)
                
                # Вычисляем RTT
                rtt = (time.time() - start_time) * 1000  # в миллисекундах
                rtts.append(rtt)
                packets_received += 1
                
                print(f'64 bytes from {host}:{port}: seq={i + 1} time={rtt:.2f} ms')
                
            except socket.timeout:
                print(f'Request timeout for seq {i + 1}')
                
            # Пауза между пингами
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nПинг прерван")
    
    finally:
        client_socket.close()
        
        # Выводим статистику
        print('\n--- Статистика пинга ---')
        if rtts:
            print(f'Packets: Sent = {packets_sent}, Received = {packets_received}, '
                  f'Lost = {packets_sent - packets_received} '
                  f'({((packets_sent - packets_received) / packets_sent * 100):.1f}% loss)')
            print(f'RTT min/avg/max = {min(rtts):.2f}/{statistics.mean(rtts):.2f}/{max(rtts):.2f} ms')
        else:
            print('Нет успешных ответов')

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print('Использование: python udp_ping_client.py хост порт')
        sys.exit(1)
        
    host = sys.argv[1]
    port = int(sys.argv[2])
    ping(host, port)