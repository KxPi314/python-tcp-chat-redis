from redis import Redis
import bcrypt
import os

class db_handler:
    redis_port = 6379
    r: Redis

    def __init__(self):
        redis_host = os.getenv("REDIS_HOST", "localhost")
        try:
            self.r = Redis(
                host=redis_host, 
                port=self.redis_port, 
                decode_responses=True
            )
            self.r.ping()
        except Exception as e:
            print(f"Error occurred while connecting to redis db: {e}")
            
    def user_login_request(self, user_login, user_password):
        user_id = self.r.hget("users:by_login", user_login)
        if not user_id:
            return False, None
        credentials = self.r.hgetall(f"user:{user_id}:credentials")
        db_password = credentials.get("password")
        
        if bcrypt.checkpw(user_password.encode('utf-8'), db_password.encode('utf-8')):
            return True, user_id
        else:
            return False, None

    def add_new_account(self, user_login, user_password):
        user_id = self.r.incr("user:id_counter")
        id_assigned = self.r.hsetnx("users:by_login", user_login, user_id)
        if not id_assigned:
            return False

        salt = bcrypt.gensalt()
        hashed_pw = bcrypt.hashpw(user_password.encode('utf-8'), salt)
        self.r.hset(f"user:{user_id}:credentials", mapping={
            "login": user_login,
            "password": hashed_pw.decode('utf-8')
        })
        self.r.sadd("users:all", user_id)
        return True


    def receive_msg(self, chat_name, msg_content, user_id):
        chat_id = self.r.hget("chats:by_name", chat_name)
        if chat_id and self.r.sismember(f"chat:{chat_id}:members", user_id):
            sender_login = self.r.hget(f"user:{user_id}:credentials", "login")
            payload = {
                "user_id": user_id,
                "user": sender_login,
                "message": msg_content,
            }
            msg_id = self.r.xadd(f"chat:{chat_id}:messages", payload, id="*", maxlen=1000, approximate=True)
            members = list(self.r.smembers(f"chat:{chat_id}:members"))
            return True, members
        return False, None


    def delete_user_account(self, user_id):
        self.r.srem("users:all", user_id)
        user_login = self.r.hget(f"user:{user_id}:credentials", "login")
        self.r.hdel("users:by_login", user_login)
        chat_id = self.r.spop(f"user:{user_id}:chats")
        while chat_id:
            self.r.srem(f"chat:{chat_id}:members",user_id)
            chat_id = self.r.spop(f"user:{user_id}:chats")
        self.r.delete(f"user:{user_id}:credentials")
        return True, "user_removed"


    def chat_sync(self, chat_name, user_id, limit: int, newest_message_id_known: int):
        chat_id = self.r.hget("chats:by_name", chat_name)
        if not(chat_id and self.r.sismember(f"chat:{chat_id}:members", user_id)):
            return False, None
        data = self.r.xread({f"chat:{chat_id}:messages" : {newest_message_id_known}},count=limit)
        return True, data 

    def chat_history(self, chat_name, user_id,limit:int, last_message_id_seen:int):
        chat_id = self.r.hget("chats:by_name", chat_name)
        if not(chat_id and self.r.sismember(f"chat:{chat_id}:members", user_id)):
            return False, None
        
        if last_message_id_seen == "+":
            max_val = "+"
        else:
            max_val = f"({last_message_id_seen}"

        data = self.r.xrevrange(
            f"chat:{chat_id}:messages",
            max=max_val,
            min="-",
            count=limit
        )
        return True, data


    def get_chat_user_list(self, chat_name, user_id):
        chat_id = self.r.hget("chats:by_name", chat_name)
        if chat_id and self.r.sismember(f"chat:{chat_id}:members", user_id):
            members_id = self.r.smembers(f"chat:{chat_id}:members")
            members_list = []
            for m_id in members_id:
                m_login = self.r.hget(f"user:{m_id}:credentials", "login")
                members_list.append(m_login)
            return True, members_list
        return False, []
    

    def add_new_chat(self, chat_name, user_id, new_members_logins: list[str]):
        if self.r.hexists("chats:by_name",chat_name):
            return False, []
        
        chat_id = self.r.incr("chat:id_counter")
        id_assigned = self.r.hsetnx("chats:by_name", chat_name, chat_id)
        
        if not id_assigned:
            return False, []
        
        self.r.hsetnx("chats:by_id", chat_id, chat_name)
        self.r.sadd(f"chat:{chat_id}:members",user_id)
        self.r.sadd(f"user:{user_id}:chats", chat_id)
        users_to_notify = [user_id] 

        for member_login in new_members_logins:
            new_member_id = self.r.hget("users:by_login", member_login)
            if new_member_id:
                users_to_notify.append(new_member_id)
                self.r.sadd(f"chat:{chat_id}:members",new_member_id)
                self.r.sadd(f"user:{new_member_id}:chats", chat_id)
            else:
                print(f"Ostrzeżenie: Nie znaleziono użytkownika o loginie {member_login}")
        return True, users_to_notify

      
    def add_user_to_chat(self, chat_name, user_id, new_member_name):        
        chat_id = self.r.hget("chats:by_name", chat_name)
        new_member_id = self.r.hget("users:by_login", new_member_name)
        if not chat_id or not new_member_id:
            return False, -1
        if not self.r.sismember(f"chat:{chat_id}:members", user_id):
            return False, -1
        self.r.sadd(f"user:{new_member_id}:chats", chat_id)
        self.r.sadd(f"chat:{chat_id}:members",new_member_id)
        return True, new_member_id


    def delete_user_from_chat(self, chat_name, user_id, old_member_name):
        chat_id = self.r.hget("chats:by_name", chat_name)
        old_member_id = self.r.hget("users:by_login", old_member_name)
        if not chat_id or not old_member_id:
            return False ,"args error"
        if not self.r.sismember(f"chat:{chat_id}:members", user_id):
            return False, "not a member"
        result = self.r.srem(f"chat:{chat_id}:members",old_member_id)
        self.r.srem(f"user:{old_member_id}:chats",chat_id)
        if not result:
            return False ,"cant remove from this chat"
        members_left = self.r.scard(f"chat:{chat_id}:members")
        if members_left == 0:
            self.del_chat(chat_id)
        return True, "user deleted"
    
    def get_user_list(self):
        return True, self.r.hkeys("users:by_login")

    def get_username_by_id(self, user_id):
        return self.r.hget(f"user:{user_id}:credentials", "login")

    def get_user_chats(self, user_id):
        all_chats_ids = self.r.smembers(f"user:{user_id}:chats")
        chats_list = []
        for chat_id in all_chats_ids:
            chat_name = self.r.hget("chats:by_id", chat_id)
            if chat_name:
                chats_list.append(chat_name)
        return True, chats_list

    def del_chat(self, chat_id):
        chat_name = self.r.hget("chats:by_id", chat_id)
        self.r.hdel("chats:by_name", chat_name)
        self.r.hdel("chats:by_id", chat_id)
        self.r.delete(f"chat:{chat_id}:messages")
        self.r.delete(f"chat:{chat_id}:members") # Dla pewności

            
# Users:

#     user:id_counter (String) –  ID counter.

#     users:by_name (Hash) – Key: name, Value: id.

#     user:{id}:credentials (Hash) – Login: xyz, Password: ***.

#     user:{id}:chats (Set) – chats ID-s.

#     users:all (Set) – Users ID set.

# Chats:

#     chat:id_counter (String) – ID counter.

#     chats:by_name (Hash) – Key: name, Value: id.
#     chats:by_id (Hash) – Key: id, Value: name.

#     chat:{id}:members (Set) – ID-s of chat members.

#     chat:{id}:messages (Stream) – chat log.