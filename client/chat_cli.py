import socket
import threading
import json
from queue import Queue

class Client:
    def __init__(self, host: str = 'localhost', port: int = 50000):
        self.host = host
        self.port = port
        self.socket = None
        self.is_connected = False
        self.notifications = Queue(maxsize=256)
        self.server_responses = Queue(maxsize=256)

    def connect(self) -> bool:
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.is_connected = True
            
            t = threading.Thread(target=self._server_listener, daemon=True)
            t.start()
            print(f"Connected to server {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"Connection Error: {e}")
            self.is_connected = False
            if self.socket:
                self.socket.close()
            return False

    def _recv_exactly(self, sock: socket.socket, n_bytes: int) -> bytes | None:
        data = b''
        while len(data) < n_bytes:
            try:
                chunk = sock.recv(n_bytes - len(data))
                if not chunk:
                    return None
                data += chunk
            except (socket.timeout, OSError):
                return None
        return data

    def _server_listener(self):
        try:
            while self.is_connected:
                header = self._recv_exactly(self.socket, 4)
                if not header:
                    break
                
                header_str = header.decode('utf-8')
                if not header_str.isdigit():
                    print(f"Protocol error invalid header {header_str}")
                    break

                package_size = int(header_str)
                payload_bytes = self._recv_exactly(self.socket, package_size)
                if not payload_bytes:
                    break

                self._handle_incoming_payload(payload_bytes.decode('utf-8'))
        except (ConnectionResetError, socket.timeout, Exception) as e:
            print(f"Disconnected / listening error: {e}")
        finally:
            self.disconnect()

    def _handle_incoming_payload(self, response_str: str):
        try:
            data = json.loads(response_str)
            status = data.get("status")
            if status == "notification":
                self.notifications.put(data.get("msg"))
            else:
                success = (status == "success")
                self.server_responses.put((success, data))
        except json.JSONDecodeError as e:
            print(f"JSON parsing Error: {e}")

    def _send_payload(self, action: str, payload: dict):
        if not self.is_connected or not self.socket:
            return
        try:
            message = json.dumps({"action": action, "payload": payload}).encode('utf-8')
            full_packet = f"{len(message):04d}".encode('utf-8') + message
            self.socket.sendall(full_packet)
        except (BrokenPipeError, ConnectionResetError, OSError) as e:
            print(f"Payload sending Error: {e}")
            self.disconnect()

    def get_response(self):
        return self.server_responses.get()

    def get_notification(self):
        return self.notifications.get()

    def send_login_request(self, user_login: str, user_password: str):
        self._send_payload("login", {"username": user_login, "password": user_password})

    def send_register_request(self, user_login: str, user_password: str):
        self._send_payload("register", {"username": user_login, "password": user_password})

    def send_msg_request(self, chat_name: str, text: str):
        self._send_payload("msg", {"text": text, "to_chat": chat_name})

    def send_del_account_request(self, reason: str = "None"):
        self._send_payload("delete_account", {"reason": reason})

    def send_del_from_chat_request(self, chat_name: str, user_name: str):
        self._send_payload("del_from_chat", {"chat_name": chat_name, "user_name": user_name})

    def send_chat_sync_request(self, chat_name: str, newest_message_id_known: str, limit: int = 20):
        self._send_payload("sync_chat", {
            "chat_name": chat_name,
            "limit": limit,
            "newest_message_id_known": str(newest_message_id_known)
        })

    def send_chat_history_request(self, chat_name: str, last_message_id_seen: str, limit: int = 20):
        self._send_payload("chat_history", {
            "chat_name": chat_name,
            "limit": limit,
            "last_message_id_seen": str(last_message_id_seen)
        })

    def send_new_chat_request(self, chat_name: str, user_list: list[str]):
        self._send_payload("new_chat", {"chat_name": chat_name, "members": user_list})

    def send_add_to_chat_request(self, chat_name: str, user_name: str):
        self._send_payload("add_to_chat", {"chat_name": chat_name, "user_name": user_name})

    def send_user_list_request(self):
        self._send_payload("users_list", {})

    def send_chats_list_request(self):
        self._send_payload("chats_list", {})

    def send_chat_members_list_request(self, chat_name: str):
        self._send_payload("chat_members_list", {"chat_name": chat_name})

    def disconnect(self):
        self.is_connected = False
        if self.socket:
            try:
                self.socket.close()
            except OSError:
                pass
            self.socket = None