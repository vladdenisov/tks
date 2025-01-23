from socket import *
import os
import sys
import struct
import time
import select
import binascii
import socket
import array

ICMP_ECHO_REQUEST = 8
MAX_HOPS = 30
TIMEOUT = 5.0
TRIES = 2

def checksum(data):
    """Вычисляет контрольную сумму пакета"""
    if len(data) % 2 == 1:
        data += b'\0'
    words = array.array('H', data)
    sum = 0
    for word in words:
        sum += word
    sum = (sum >> 16) + (sum & 0xffff)
    sum += (sum >> 16)
    return (~sum) & 0xffff

def build_packet():
    """Создает ICMP пакет"""
    # ID процесса (16 бит)
    my_id = os.getpid() & 0xFFFF

    # Заголовок: тип (8), код (8), контрольная сумма (16), ID (16), порядковый номер (16)
    header = struct.pack('bbHHh', ICMP_ECHO_REQUEST, 0, 0, my_id, 1)

    # Данные пакета: метка времени
    data = struct.pack('d', time.time())

    # Вычисляем контрольную сумму
    my_checksum = checksum(header + data)

    # Собираем заголовок с контрольной суммой
    header = struct.pack('bbHHh', ICMP_ECHO_REQUEST, 0, 
                        socket.htons(my_checksum), my_id, 1)

    # Возвращаем полный пакет
    return header + data

def get_host_name(ip_addr):
    """Получает имя хоста по IP-адресу"""
    try:
        host_info = gethostbyaddr(ip_addr)
        return host_info[0]
    except herror:
        return ip_addr

def get_route(hostname):
    """Выполняет трассировку маршрута до указанного хоста"""
    print(f"\nТрассировка маршрута к {hostname}")
    print(f"максимум {MAX_HOPS} прыжков:\n")

    timeLeft = TIMEOUT
    
    for ttl in range(1, MAX_HOPS + 1):
        for tries in range(TRIES):
            try:
                destAddr = gethostbyname(hostname)
            except gaierror:
                print(f"Не удалось разрешить имя хоста {hostname}")
                return

            # Создаем сырой сокет ICMP
            try:
                icmp = socket.getprotobyname("icmp")
                mySocket = socket.socket(socket.AF_INET, socket.SOCK_RAW, icmp)
            except socket.error as e:
                if e.errno == 1:
                    print("Операция требует повышенных привилегий (запустите от имени администратора)")
                    sys.exit()
                raise

            # Устанавливаем TTL и таймаут
            mySocket.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, struct.pack('I', ttl))
            mySocket.settimeout(TIMEOUT)

            try:
                # Отправляем пакет
                packet = build_packet()
                mySocket.sendto(packet, (hostname, 0))
                start_time = time.time()

                # Ожидаем ответ
                whatReady = select.select([mySocket], [], [], timeLeft)
                if whatReady[0] == []:
                    print(f" {ttl}  * * *  Превышен интервал ожидания запроса")
                    break

                # Получаем ответ
                recvPacket, addr = mySocket.recvfrom(1024)
                time_received = time.time()

                # Извлекаем тип ICMP из ответа (9-й байт IP-пакета)
                icmp_type = recvPacket[20]

                if icmp_type == 11:  # Time Exceeded
                    # Получаем имя хоста
                    host_name = get_host_name(addr[0])
                    print(f" {ttl}  {addr[0]} ({host_name})  {(time_received - start_time)*1000:.0f} мс")
                    
                elif icmp_type == 3:  # Destination Unreachable
                    host_name = get_host_name(addr[0])
                    print(f" {ttl}  {addr[0]} ({host_name})  {(time_received - start_time)*1000:.0f} мс")
                    print("Достигнут недоступный хост")
                    return

                elif icmp_type == 0:  # Echo Reply
                    host_name = get_host_name(addr[0])
                    print(f" {ttl}  {addr[0]} ({host_name})  {(time_received - start_time)*1000:.0f} мс")
                    print("\nТрассировка завершена.")
                    return

                else:
                    print(f"Получен неожиданный тип ICMP: {icmp_type}")
                    break

            except socket.timeout:
                continue
            except socket.error as e:
                print(f"Ошибка сокета: {e}")
                break
            finally:
                mySocket.close()
                
def main():
    if len(sys.argv) < 2:
        print('Использование: python traceroute.py hostname')
        sys.exit(1)
        
    hostname = sys.argv[1]
    get_route(hostname)

if __name__ == '__main__':
    main()