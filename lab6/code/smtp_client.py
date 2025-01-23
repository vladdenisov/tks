from socket import *
import ssl
import base64
import mimetypes
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.base import MIMEBase
from email import encoders
import argparse
from getpass import getpass
from dotenv import load_dotenv
from pathlib import Path

class SMTPClient:
    def __init__(self, server="smtp.gmail.com", port=587):
        self.server = server
        self.port = port
        self.client_socket = None
        self.ssl_socket = None
    
    def connect(self):
        """Установка начального TCP-соединения"""
        try:
            self.client_socket = socket(AF_INET, SOCK_STREAM)
            self.client_socket.connect((self.server, self.port))
            response = self.receive_response()
            print(f"Соединение установлено: {response}")
            return response.startswith('220')
        except Exception as e:
            print(f"Ошибка подключения: {e}")
            return False

    def start_tls(self):
        """Инициализация TLS-соединения"""
        try:
            # Сначала выполняем EHLO
            client_fqdn = self.get_fqdn()
            if not self.send_command(f"EHLO {client_fqdn}", '250'):
                # Если EHLO не сработал, пробуем HELO
                if not self.send_command(f"HELO {client_fqdn}", '250'):
                    print("Ошибка: Не удалось выполнить EHLO/HELO")
                    return False
            
            # Отправляем STARTTLS
            self.send_command("STARTTLS", '220')
            
            # Создаем SSL-обертку
            context = ssl.create_default_context()
            self.ssl_socket = context.wrap_socket(self.client_socket, 
                                                server_hostname=self.server)
            
            # После установки TLS нужно снова выполнить EHLO
            if not self.send_command(f"EHLO {client_fqdn}", '250'):
                print("Ошибка: Не удалось выполнить EHLO после TLS")
                return False
                
            return True
            
        except Exception as e:
            print(f"Ошибка при установке TLS: {e}")
            return False

    def get_fqdn(self):
        """Получение полного доменного имени или IP-адреса"""
        try:
            import socket
            # Пытаемся получить полное доменное имя
            fqdn = socket.getfqdn()
            # Если не удалось получить FQDN, используем IP-адрес
            if fqdn == 'localhost' or '.' not in fqdn:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(('8.8.8.8', 80))
                return s.getsockname()[0]
                s.close()
            return fqdn
        except Exception:
            # В случае ошибки возвращаем локальный IP
            return '127.0.0.1'

    def login(self, username, password):
        """Аутентификация на сервере"""
        try:
            # AUTH LOGIN
            if not self.send_command("AUTH LOGIN", '334'):
                print("Ошибка: сервер не принял команду AUTH LOGIN")
                return False

            # Отправляем username в base64
            encoded_username = base64.b64encode(username.encode()).decode()
            if not self.send_command(encoded_username, '334'):
                print("Ошибка: сервер не принял имя пользователя")
                return False

            # Отправляем password в base64
            encoded_password = base64.b64encode(password.encode()).decode()
            if not self.send_command(encoded_password, '235'):
                print("Ошибка: неверные учетные данные")
                return False

            return True

        except Exception as e:
            print(f"Ошибка при аутентификации: {e}")
            return False

            # Отправляем AUTH LOGIN
            self.send_command("AUTH LOGIN")
            if not self.check_response('334'):
                return False

            # Отправляем username в base64
            self.ssl_socket.send(base64.b64encode(username.encode()) + b'\r\n')
            if not self.check_response('334'):
                return False

            # Отправляем password в base64
            self.ssl_socket.send(base64.b64encode(password.encode()) + b'\r\n')
            return self.check_response('235')

        except Exception as e:
            print(f"Ошибка при аутентификации: {e}")
            return False

    def send_email(self, from_addr, to_addr, subject, message, attachments=None):
        """Отправка email с вложениями"""
        try:
            # Создаем MIME-сообщение
            msg = MIMEMultipart()
            msg['From'] = from_addr
            msg['To'] = to_addr
            msg['Subject'] = subject

            # Добавляем текст
            msg.attach(MIMEText(message, 'plain'))

            # Добавляем вложения
            if attachments:
                for file_path in attachments:
                    if os.path.exists(file_path):
                        content_type, _ = mimetypes.guess_type(file_path)
                        maintype, subtype = content_type.split('/') if content_type else ('application', 'octet-stream')

                        with open(file_path, 'rb') as f:
                            if maintype == 'image':
                                img = MIMEImage(f.read(), _subtype=subtype)
                                img.add_header('Content-Disposition', 'attachment', filename=os.path.basename(file_path))
                                msg.attach(img)
                            else:
                                part = MIMEBase(maintype, subtype)
                                part.set_payload(f.read())
                                encoders.encode_base64(part)
                                part.add_header('Content-Disposition', 'attachment', filename=os.path.basename(file_path))
                                msg.attach(part)

            # Отправляем MAIL FROM
            if not self.send_command(f"MAIL FROM:<{from_addr}>", '250'):
                return False

            # Отправляем RCPT TO
            if not self.send_command(f"RCPT TO:<{to_addr}>", '250'):
                return False

            # Отправляем DATA
            if not self.send_command("DATA", '354'):
                return False

            # Отправляем содержимое письма
            email_content = msg.as_string() + '\r\n.\r\n'
            self.ssl_socket.send(email_content.encode())
            
            # Проверяем финальный ответ
            if not self.check_response('250'):
                print("Ошибка: Сервер не подтвердил получение письма")
                return False

            print("Письмо успешно отправлено!")
            return True

        except Exception as e:
            print(f"Ошибка при отправке письма: {e}")
            return False

    def quit(self):
        """Завершение сессии"""
        try:
            if self.ssl_socket:
                self.send_command("QUIT")
                self.ssl_socket.close()
            if self.client_socket:
                self.client_socket.close()
        except Exception as e:
            print(f"Ошибка при закрытии соединения: {e}")

    def send_command(self, command, expected_code='250', hide_in_logs=False):
        """
        Отправка команды на сервер
        :param command: Команда для отправки
        :param expected_code: Ожидаемый код ответа
        :param hide_in_logs: Скрывать ли команду в логах (для паролей)
        """
        try:
            socket_to_use = self.ssl_socket if self.ssl_socket else self.client_socket
            socket_to_use.send((command + '\r\n').encode())
            
            # Получаем ответ
            response = self.receive_response(hide_in_logs)
            
            # Проверяем код ответа
            response_code = response[:3] if response else ''
            
            # Логируем результат
            if not hide_in_logs:
                if response_code != expected_code:
                    print(f"Команда: {command}")
                    print(f"Ожидался код: {expected_code}")
                    print(f"Получен ответ: {response.strip()}")
            
            return response_code == expected_code
            
        except Exception as e:
            print(f"Ошибка при отправке команды: {e}")
            return False
            
    def receive_response(self, hide_in_logs=False):
        """Получение ответа от сервера"""
        try:
            socket_to_use = self.ssl_socket if self.ssl_socket else self.client_socket
            response = socket_to_use.recv(1024).decode()
            
            if not hide_in_logs:
                print(f"Ответ сервера: {response.strip()}")
                
            return response
            
        except Exception as e:
            print(f"Ошибка при получении ответа: {e}")
            return ''

    def check_response(self, expected_code):
        """Проверка кода ответа"""
        response = self.receive_response()
        return response.startswith(expected_code)

def load_env_config():
    """Загрузка конфигурации из .env файла"""
    # Пытаемся найти .env файл в текущей директории или родительских директориях
    env_path = Path('.env')
    parent_env_path = Path('../.env')
    
    if env_path.exists():
        load_dotenv(env_path)
    elif parent_env_path.exists():
        load_dotenv(parent_env_path)
    else:
        print("Внимание: .env файл не найден")
    
    # Получаем значения из окружения
    config = {
        'server': os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
        'port': int(os.getenv('SMTP_PORT', '587')),
        'username': os.getenv('SMTP_USERNAME'),
        'password': os.getenv('SMTP_PASSWORD'),
        'default_from': os.getenv('DEFAULT_FROM'),
        'default_to': os.getenv('DEFAULT_TO')
    }
    
    return config

def main():
    # Загружаем конфигурацию из .env
    config = load_env_config()
    
    parser = argparse.ArgumentParser(description='SMTP клиент с поддержкой TLS и вложений')
    parser.add_argument('--server', default=config['server'], help='SMTP сервер')
    parser.add_argument('--port', type=int, default=config['port'], help='Порт сервера')
    parser.add_argument('--username', default=config['username'], help='Email отправителя')
    parser.add_argument('--to', default=config['default_to'], help='Email получателя')
    parser.add_argument('--subject', required=True, help='Тема письма')
    parser.add_argument('--message', required=True, help='Текст письма')
    parser.add_argument('--attachments', nargs='*', help='Пути к файлам вложений')
    parser.add_argument('--no-env', action='store_true', help='Игнорировать .env файл')

    args = parser.parse_args()

    # Определяем пароль
    password = None
    if not args.no_env and config['password']:
        password = config['password']
    
    # Если пароль не найден в .env, запрашиваем его
    if not password:
        password = getpass('Введите пароль: ')
    
    # Проверяем обязательные параметры
    if not args.username:
        print("Ошибка: не указан email отправителя")
        return
    
    if not args.to:
        print("Ошибка: не указан email получателя")
        return

    # Создаем клиент
    client = SMTPClient(args.server, args.port)

    try:
        # Устанавливаем соединение
        if not client.connect():
            return

        # Включаем TLS
        if not client.start_tls():
            return

        # Авторизуемся
        if not client.login(args.username, password):
            return

        # Отправляем письмо
        if client.send_email(args.username, args.to, args.subject, args.message, args.attachments):
            print("Письмо успешно отправлено!")
        else:
            print("Ошибка при отправке письма")

    finally:
        client.quit()

if __name__ == '__main__':
    main()