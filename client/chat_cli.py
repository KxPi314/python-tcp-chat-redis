import socket
import sys
import threading
import json
from queue import Queue

class Client:
    def __init__(self, host='localhost', port=50000):
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.notifications = Queue(maxsize=256)
        self.server_responses = Queue(maxsize=256)
       
    def connect(self):
        try:
            self.socket.connect((self.host, self.port))
            print(f"Połączono z serwerem {self.host}:{self.port}")
            t = threading.Thread(target=self.server_listener)
            t.daemon = True
            t.start()
        except Exception as e:
            print(f"Nie udało się połączyć: {e}")
            sys.exit(1)

    def server_listener(self):
        print(f"Communication with server started") 
        try:
            while True:
                package_size = self.recv_exactly(self.socket, 4)
                if not package_size:
                    break
                package_size = package_size.decode("utf-8")
                if not package_size.isdigit():
                        print(f"communication error from: invalid header {package_size}")
                        break
                try:
                    package_size = int(package_size)
                except ValueError:
                    print ("Error reading package header")
                    break

                request = self.recv_exactly(self.socket, package_size)
                if not request:
                    break
                if len(request) != package_size:
                    print("Error package_size doesnt match")
                request = request.decode('utf-8')
                
                valid = self.groupe_server_msg(request)
                if not valid:
                    print("Error cant parse server msg")
                    continue
        except (ConnectionResetError, socket.timeout, Exception) as e:
            print(f"disconnected/error: {e}")
        finally:
            self.socket.close()

    def recv_exactly(self, sock, n_bytes):
            data = b''
            while len(data) < n_bytes:
                try:
                    chunk = sock.recv(n_bytes - len(data))
                    if not chunk:
                        return None
                    data += chunk
                except socket.timeout:
                    return None
            return data

    def groupe_server_msg(self, response):
        try:
            data = json.loads(response)
            status = data.get("status")
            
            if status == "notification":
                self.notifications.put(data.get("msg"))
            else:
                success = (status == "success")
                self.server_responses.put((success, data))
            return True
        except Exception as e:
            print(f"Error parsing server response: {e}")
            return False
        
    def get_response(self):
        return self.server_responses.get()

    def get_notification(self):
        return self.notifications.get()

    def send_login_request(self, user_login: str, user_password: str):
        message = json.dumps({
            "action": "login",
            "payload" : {
                "username" : user_login,
                "password" : user_password
                }
            }).encode('utf-8')
        self.socket.sendall(f"{len(message):04d}".encode('utf-8')+message)
        
    def send_register_request(self, user_login: str, user_password: str):
        message = json.dumps({
            "action": "register",
            "payload" : {
                "username" : user_login,
                "password" : user_password
                }
            }).encode('utf-8')
        self.socket.sendall(f"{len(message):04d}".encode('utf-8')+message)
        

    def send_msg_request(self, chat_name, text):
        message = json.dumps({
            "action": "msg",
            "payload" : {
                "text" : text,
                "to_chat" : chat_name
                }
            }).encode('utf-8')
        self.socket.sendall(f"{len(message):04d}".encode('utf-8')+message)

    def send_del_account_request(self, reason = "None"):
        message = json.dumps({
            "action": "delete_account",
            "payload" : {
                "reason" : reason
                }
            }).encode('utf-8')
        self.socket.sendall(f"{len(message):04d}".encode('utf-8')+message)
        

    def send_del_from_chat_request(self, chat_name, user_name):
        message = json.dumps({
            "action": "del_from_chat",
            "payload" : {
                "chat_name" : chat_name,
                "user_name": user_name
                }
            }).encode('utf-8')
        self.socket.sendall(f"{len(message):04d}".encode('utf-8')+message)
     

    def send_chat_sync_request(self, chat_name, newest_message_id_known, limit = 20):
        message = json.dumps({
            "action": "sync_chat",
            "payload" : {
                "chat_name" : chat_name,
                "limit": limit,
                "newest_message_id_known": newest_message_id_known
                }
            }).encode('utf-8')
        self.socket.sendall(f"{len(message):04d}".encode('utf-8')+message)
     

    def send_chat_history_request(self, chat_name, last_message_id_seen, limit = 20):
        message = json.dumps({
            "action": "chat_history",
            "payload" : {
                "chat_name" : chat_name,
                "limit": limit,
                "last_message_id_seen": last_message_id_seen
                }
                }).encode('utf-8')
        self.socket.sendall(f"{len(message):04d}".encode('utf-8')+message)

    def send_new_chat_request(self, chat_name: str, user_list: list[str]):
        message = json.dumps({
            "action": "new_chat",
            "payload" : {
                "chat_name" : chat_name,
                "members": user_list
                }
            }).encode('utf-8')
        self.socket.sendall(f"{len(message):04d}".encode('utf-8')+message)

    def send_add_to_chat_request(self, chat_name: str, user_name: str):
        message = json.dumps({
            "action": "add_to_chat",
            "payload" : {
                "chat_name" : chat_name,
                "user_name": user_name
                }
            }).encode('utf-8')
        self.socket.sendall(f"{len(message):04d}".encode('utf-8')+message)
        
    def send_user_list_request(self):
        message = json.dumps({"action": "users_list", "payload": {}}).encode('utf-8')
        self.socket.sendall(f"{len(message):04d}".encode('utf-8')+message)
        
    def send_chats_list_request(self):
        message = json.dumps({"action": "chats_list", "payload": {}}).encode('utf-8')
        self.socket.sendall(f"{len(message):04d}".encode('utf-8')+message)
    
    def send_chat_members_list_request(self, chat_name):
        message = json.dumps({
            "action": "chat_members_list", 
            "payload": {"chat_name": chat_name}
        }).encode('utf-8')
        self.socket.sendall(f"{len(message):04d}".encode('utf-8')+message)

    def disconnect(self):
        self.socket.close()