from socket import *
import os
import sys
import struct
import time
import select
import statistics
import array

class ICMPPing:
    def __init__(self, timeout=1):
        self.timeout = timeout
        self.sequence = 0
        self.stats = {
            'sent': 0,
            'received': 0,
            'rtts': [],
            'errors': {}
        }
        
        # Коды ошибок ICMP
        self.icmp_errors = {
            0: "Эхо-ответ",
            3: {
                0: "Сеть недоступна",
                1: "Хост недоступен",
                2: "Протокол недоступен",
                3: "Порт недоступен",
                4: "Требуется фрагментация, но установлен флаг DF",
                5: "Ошибка в маршруте отправителя",
                6: "Сеть назначения неизвестна",
                7: "Хост назначения неизвестен",
                8: "Хост-отправитель изолирован",
                9: "Сеть административно запрещена",
                10: "Хост административно запрещен",
                11: "Сеть недоступна для данного типа обслуживания",
                12: "Хост недоступен для данного типа обслуживания",
                13: "Связь административно запрещена фильтром",
                14: "Нарушение приоритета хоста",
                15: "Приоритет отключен"
            },
            11: "Превышено время"
        }

    def checksum(self, data):
        """Вычисляет контрольную сумму данных"""
        if len(data) % 2 == 1:
            data += b'\0'
        words = array.array('H', data)
        sum = 0
        for word in words:
            sum += word
        sum = (sum >> 16) + (sum & 0xffff)
        sum += (sum >> 16)
        return (~sum) & 0xffff

    def create_packet(self, id):
        """Создает ICMP пакет"""
        # Увеличиваем номер последовательности
        self.sequence += 1
        
        # Заголовок: тип (8), код (8), контрольная сумма (16), id (16), sequence (16)
        header = struct.pack('bbHHh', 8, 0, 0, id, self.sequence)
        
        # Данные: текущее время
        data = struct.pack('d', time.time())
        
        # Вычисляем контрольную сумму
        my_checksum = self.checksum(header + data)
        
        # Создаем заголовок с правильной контрольной суммой
        header = struct.pack('bbHHh', 8, 0, htons(my_checksum), id, self.sequence)
        
        return header + data

    def parse_icmp_reply(self, recv_packet):
        """Разбирает ICMP ответ"""
        icmp_header = recv_packet[20:28]
        type, code, checksum, id, sequence = struct.unpack('bbHHh', icmp_header)
        
        if type == 0:  # Echo Reply
            time_sent = struct.unpack('d', recv_packet[28:36])[0]
            return type, code, id, sequence, time_sent
        else:
            # Для других типов ICMP сообщений извлекаем оригинальный пакет
            orig_packet = recv_packet[48:56]  # Пропускаем IP+ICMP заголовки
            try:
                time_sent = struct.unpack('d', orig_packet)[0]
            except struct.error:
                time_sent = None
            return type, code, id, sequence, time_sent

    def receive_ping(self, my_socket, process_id, timeout):
        """Получает ответ на пинг"""
        time_left = timeout
        
        while time_left > 0:
            started_select = time.time()
            ready = select.select([my_socket], [], [], time_left)
            how_long_in_select = time.time() - started_select
            
            if not ready[0]:  # Таймаут
                return None, "Превышен интервал ожидания", None
                
            time_received = time.time()
            
            try:
                recv_packet, addr = my_socket.recvfrom(1024)
                type, code, recv_id, sequence, time_sent = self.parse_icmp_reply(recv_packet)
                
                if recv_id == process_id:  # Проверяем, что это ответ на наш запрос
                    if type == 0:  # Echo Reply
                        delay = (time_received - time_sent) * 1000  # в миллисекундах
                        ttl = struct.unpack('b', recv_packet[8:9])[0]  # TTL из IP заголовка
                        return addr[0], delay, ttl
                    else:
                        error_msg = self.get_error_message(type, code)
                        return addr[0], error_msg, None
                        
            except Exception as e:
                print(f"Ошибка при получении пакета: {e}")
                return None, f"Ошибка: {e}", None
            time_left = time_left - how_long_in_select
            if time_left <= 0:
                return None, "Превышен интервал ожидания", None

    def get_error_message(self, type, code):
        """Возвращает сообщение об ошибке для ICMP типа и кода"""
        if type in self.icmp_errors:
            if isinstance(self.icmp_errors[type], dict):
                return self.icmp_errors[type].get(code, f"Неизвестный код {code}")
            return self.icmp_errors[type]
        return f"Неизвестный тип ICMP {type}"

    def do_one_ping(self, dest_addr):
        """Выполняет один пинг"""
        try:
            icmp = getprotobyname("icmp")
            my_socket = socket(AF_INET, SOCK_RAW, icmp)
        except error as e:
            if e.errno == 1:
                print("Операция требует привилегий root")
                sys.exit(1)
            return None, f"Ошибка сокета: {e}", None
            
        my_id = os.getpid() & 0xFFFF
        packet = self.create_packet(my_id)
        
        # Отправляем пакет
        self.stats['sent'] += 1
        my_socket.sendto(packet, (dest_addr, 1))
        
        # Получаем ответ
        result = self.receive_ping(my_socket, my_id, self.timeout)
        my_socket.close()
        
        if result[1] is not None and isinstance(result[1], float):
            self.stats['received'] += 1
            self.stats['rtts'].append(result[1])
            
        return result

    def ping(self, host, count=4):
        """Выполняет серию пингов"""
        try:
            dest_addr = gethostbyname(host)
            print(f"\nPing {host} [{dest_addr}]")
        except gaierror:
            print(f"Не удалось разрешить имя хоста {host}")
            return
            
        for i in range(count):
            addr, result, ttl = self.do_one_ping(dest_addr)
            
            if addr is None:
                print(f"Ошибка: {result}")
                if result not in self.stats['errors']:
                    self.stats['errors'][result] = 0
                self.stats['errors'][result] += 1
            elif isinstance(result, float):
                print(f"Ответ от {addr}: время={result:.1f}мс TTL={ttl}")
            else:
                print(f"Ответ от {addr}: {result}")
                if result not in self.stats['errors']:
                    self.stats['errors'][result] = 0
                self.stats['errors'][result] += 1
                
            if i < count - 1:
                time.sleep(1)
                
        # Выводим статистику
        self.print_statistics(host)

    def print_statistics(self, host):
        """Выводит статистику пинга"""
        print(f"\nСтатистика ping для {host}:")
        print(f"    Пакетов: отправлено = {self.stats['sent']}, "
              f"получено = {self.stats['received']}, "
              f"потеряно = {self.stats['sent'] - self.stats['received']}"
              f" ({(self.stats['sent'] - self.stats['received']) / self.stats['sent'] * 100:.1f}% потерь)")
              
        if self.stats['rtts']:
            print(f"Приблизительное время приема-передачи в мс:")
            print(f"    Минимальное = {min(self.stats['rtts']):.1f}мс, "
                  f"Максимальное = {max(self.stats['rtts']):.1f}мс, "
                  f"Среднее = {statistics.mean(self.stats['rtts']):.1f}мс")
                  
        if self.stats['errors']:
            print("\nПолученные ошибки:")
            for error, count in self.stats['errors'].items():
                print(f"    {error}: {count} раз")

def main():
    if len(sys.argv) < 2:
        print('Использование: sudo python ping.py hostname')
        sys.exit(1)
        
    pinger = ICMPPing()
    pinger.ping(sys.argv[1])

if __name__ == '__main__':
    main()