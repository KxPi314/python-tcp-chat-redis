import socket
import threading
from db_handler import db_handler
import json_handler as json_handler
import json

MAX_PACKET_SIZE = 1024 * 1024 # 1mb


class ClientConnection:
    def __init__(self, sock):
        self.sock = sock
        self.send_lock = threading.Lock()

    def send_safe(self, data):
        with self.send_lock:
            try:
                self.sock.sendall(data)
                return True
            except (ConnectionResetError, BrokenPipeError):
                return False

class Server:
    com_port = 50000 
    users_dict: dict
    socket_dict: dict[str, ClientConnection]
    dbh: db_handler
    lock : threading.Lock

    def __init__(self):
        print('Starting Server!')
        self.users_dict = {}
        self.socket_dict = {}
        self.lock = threading.Lock()
        try: 
            self.dbh = db_handler()
            self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.s.bind(('', self.com_port)) 
            print('Server established!')
        except Exception as e:
            print(f"Error occurred: {e}")
            return
    
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
    
    def on_new_client(self, clientsocket, addr):
        print(f"Handler started for {addr}")
        clientsocket.settimeout(120.0) 
        try:
            while True:
                package_size = self.recv_exactly(clientsocket, 4)
                
                if not package_size:
                    break
                package_size = package_size.decode('utf-8')

                if not package_size.isdigit():
                    print(f"communication error from {addr}: invalid header {package_size}")
                    break

                try:
                    package_size = int(package_size)
                    if package_size > MAX_PACKET_SIZE:
                        print(f"User {addr} disconnected due to package size {package_size}")
                        break # Rozłącz
                except ValueError:
                    break

                request = self.recv_exactly(clientsocket, package_size)
                if not request:
                    break

                request = request.decode('utf-8')
                valid, json_handler_response = json_handler.check_request(package_size, request)
                if not valid:
                    print(json_handler_response)
                    error_response = json.dumps({"status": "error", "msg": json_handler_response})   
                    error_response = error_response.encode('utf-8')
                    clientsocket.sendall(f"{len(error_response):04d}".encode('utf-8')+error_response)
                    continue
                response = self.handle_user_request(addr, clientsocket, json_handler_response)
                if isinstance(response, bytes):
                    clientsocket.sendall(response)
                else:
                    #errors
                    error_data = response.encode('utf-8')
                    clientsocket.sendall(error_data)
                
        except (ConnectionResetError, socket.timeout, Exception) as e:
            print(f"Client {addr} disconnected/error: {e}")
        finally:
            clientsocket.close()
            with self.lock: 
                login = self.users_dict.pop(addr, None) 
                if login and login != -1:
                    self.socket_dict.pop(login, None)
            print(f"Client {addr} cleanup finished.")


    def msg_size_check(self, msg_len: int, msg: str):
        if(len(msg.encode('utf-8')) == msg_len):
            return True
        return False


    def _create_error_response(self, msg):
        body = json.dumps({"status": "error", "msg": msg}).encode("utf-8")
        header = f"{len(body):04d}".encode("utf-8")
        return header + body
    

    def _broadcast_notification(self, members_list, json_payload, exclude_user_id=None):
        msg_body = json.dumps(json_payload).encode("utf-8")
        msg_header = f"{len(msg_body):04d}".encode("utf-8")
        full_package = msg_header + msg_body
        
        sockets_to_send = []
        with self.lock:
            for member_id in members_list:
                member_id = str(member_id)
                if member_id == exclude_user_id:
                    continue
                if member_id in self.socket_dict:
                    sockets_to_send.append(self.socket_dict[member_id])

        for client_conn in sockets_to_send:
            client_conn.send_safe(full_package)


    def handle_user_request(self, addr, socket, request):
        if(request.action == 'login'):
            return self.handle_login(addr, socket, request)        
        
        if(request.action == 'register'):
            return self.handle_register(addr, request)
            
        with self.lock:
            if(self.users_dict[addr] == -1):
                return False, f"user {addr} not logged in Error."    
            user_id = self.users_dict[addr]

        match(request.action):
            case 'msg':
                return self.handle_msg(user_id, request)
            case 'new_chat':
                return self.handle_new_chat(user_id, request)
            case 'delete_account':
                return self.handle_delete_account(addr, user_id)
            case 'add_to_chat':
                return self.handle_add_to_chat(user_id, request)
            case 'del_from_chat':
                return self.handle_del_from_chat(user_id, request)
            case 'sync_chat':
                return self.handle_sync_chat(user_id, request)
            case 'chat_history':
                return self.handle_chat_history(user_id, request)
            case 'chat_members_list':
                return self.handle_chat_members_list(user_id, request)
            case 'users_list':
                return self.handle_users_list()
            case 'chats_list':
                return self.handle_chats_list(user_id)
            case _:
                return False, f" incorrect action from {addr}"


    def handle_login(self, addr, socket, request):
        success, user_id = self.dbh.user_login_request(request.payload.username, request.payload.password)
        if not success:
            return self._create_error_response("Invalid credentials")    
        
        with self.lock:
            self.users_dict[addr] = user_id
            self.socket_dict[user_id] = ClientConnection(socket)  
            print(f"User {user_id} logged in.")
        body = json.dumps({
            "status": "success",
            "action": "login",
            "msg": "logged in"
            }).encode("utf-8")
        header = f"{len(body):04d}".encode("utf-8")
        return header + body 
    

    def handle_register(self, addr, request):
        success = self.dbh.add_new_account(request.payload.username, request.payload.password)
        if not success:
            return self._create_error_response("Invalid credentials")
        
        body = json.dumps({
            "status": "success",
            "action": "register",
            "msg": "user registered"
            }).encode("utf-8")
        header = f"{len(body):04d}".encode("utf-8")
        return header + body 
    

    def handle_msg(self, user_id, request):
        success, members_id_list = self.dbh.receive_msg(request.payload.to_chat,request.payload.text, user_id)
        if not success:
            return self._create_error_response("cant send msg")
        
        sender_name = self.dbh.get_username_by_id(user_id)

        notification = {
            "status": "notification",
            "msg": {
                "type": "new_msg",
                "chat": request.payload.to_chat,
                "text": request.payload.text,
                "sender": sender_name
            }
        }
        self._broadcast_notification(members_id_list, notification, exclude_user_id=str(user_id))
        
        body = json.dumps({
            "status": "success",
            "action": "msg",
            "msg": "msg_sent"}).encode("utf-8")
        header = f"{len(body):04d}".encode("utf-8")
        return header + body
    

    def handle_new_chat(self, user_id, request):
        success, members_id_list = self.dbh.add_new_chat(request.payload.chat_name, user_id, request.payload.members)
        if not success:
            return self._create_error_response("chat name busy or error")
        
        notification = {
            "status": "notification",
            "msg": {
                "type": "new_chat",
                "name": request.payload.chat_name
            }
        }
        self._broadcast_notification(members_id_list, notification)

        body = json.dumps({
            "status": "success",
            "action": "new_chat",
            "msg": f"chat {request.payload.chat_name} created"
            }).encode("utf-8")
        header = f"{len(body):04d}".encode("utf-8")
        return header + body
    

    def handle_delete_account(self,addr, user_id):
        success , response = self.dbh.delete_user_account(user_id)
        if not success:
            return self._create_error_response(response)
        
        body = json.dumps({
            "status": "success",
            "action": "del_acc",
            "msg": "account deleted. bye!"
            }).encode("utf-8")
        header = f"{len(body):04d}".encode("utf-8")
        with self.lock:
            self.users_dict.pop(addr)
            self.socket_dict.pop(user_id)  
            print(f"User {user_id} logged in.")

        return header + body
    

    def handle_add_to_chat(self, user_id, request):
        success, _ = self.dbh.add_user_to_chat(request.payload.chat_name, user_id, request.payload.user_name)
        if not success:
            return self._create_error_response("user was not added to chat")

        _, members_list = self.dbh.get_chat_user_list(request.payload.chat_name, user_id)
        notification = {
            "status": "notification",
            "msg": {
                "type": "member_update",
                "chat": request.payload.chat_name,
                "text": f"User {request.payload.user_name} joined chat."
            }
        }
        self._broadcast_notification(members_list, notification)

        body = json.dumps({
            "status": "success",
            "action": "add_to_chat",
            "msg":f"added {request.payload.user_name} to chat"}).encode("utf-8")
        header = f"{len(body):04d}".encode("utf-8")
        return header + body
    

    def handle_del_from_chat(self, user_id, request):
        success, response = self.dbh.delete_user_from_chat(request.payload.chat_name, user_id, request.payload.user_name)
        if not success:
            return self._create_error_response(response)
        
        _, members_list = self.dbh.get_chat_user_list(request.payload.chat_name, user_id)
        
        if members_list:
            notification = {
                "status": "notification",
                "msg": {
                    "type": "member_update", 
                    "chat": request.payload.chat_name,
                    "text": f"User {request.payload.user_name} left chat."
                }
            }
            self._broadcast_notification(members_list, notification)

        body = json.dumps({
            "status": "success",
            "action": "del_from_chat",
            "msg":f"removed {request.payload.user_name} from chat"
            }).encode("utf-8")
        header = f"{len(body):04d}".encode("utf-8")
        return header + body
    

    def handle_sync_chat(self, user_id, request):
        success , response = self.dbh.chat_sync(
            request.payload.chat_name,
            user_id,
            int(request.payload.limit),
            int(request.payload.newest_message_id_known)
        )
        if not success:
             return self._create_error_response(response)
        
        body = json.dumps({
            "status": "success",
            "action": "chat_sync",
            "msg": response
            }).encode("utf-8")
        header = f"{len(body):04d}".encode("utf-8")
        return header + body
    

    def handle_chat_history(self, user_id, request):
        success , response = self.dbh.chat_history(
            request.payload.chat_name,
            user_id,
            request.payload.limit,
            request.payload.last_message_id_seen
        )
        if not success:
             return self._create_error_response(response)
        
        body = json.dumps({
            "status": "success",
            "action": "chat_his",
            "msg": response
            }).encode("utf-8")
        header = f"{len(body):04d}".encode("utf-8")
        return header + body
    

    def handle_chat_members_list(self, user_id, request):
        success, members_list = self.dbh.get_chat_user_list(request.payload.chat_name, user_id)
        if not success:
            return self._create_error_response("cant acces member list")
        
        body = json.dumps({
            "status": "success", 
            "action": "get_members",
            "msg": members_list
            }).encode("utf-8")
        header = f"{len(body):04d}".encode("utf-8")
        return header + body
    
    
    def handle_users_list(self):
        success, user_list = self.dbh.get_user_list()
        if not success:
            return self._create_error_response("cant fetch chats users list")
        
        body = json.dumps({
            "status": "success",
            "action": "get_users",
            "msg": user_list
            }).encode("utf-8")
        header = f"{len(body):04d}".encode("utf-8")
        return header + body 


    def handle_chats_list(self, user_id):
        success, chats_list = self.dbh.get_user_chats(user_id)
        if not success:
            return self._create_error_response("cant fetch chats list")
        
        body = json.dumps({
            "status": "success",
            "action": "get_chats",
            "msg": chats_list
            }).encode("utf-8")
        header = f"{len(body):04d}".encode("utf-8")
        return header + body 


    def run(self):
        self.s.listen(5)
        print('Waiting for connections...')
        while True:
            c, addr = self.s.accept()
            print('Got connection from: ', addr)
            with self.lock:
                self.users_dict[addr] = -1
            t = threading.Thread(target=self.on_new_client, args=(c, addr))
            t.daemon = True
            t.start()



if __name__ == "__main__": 
    server = Server()
    if hasattr(server, 's'):
        server.run()