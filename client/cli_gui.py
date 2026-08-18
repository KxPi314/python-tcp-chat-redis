import tkinter as tk
from tkinter import messagebox
from chat_cli import Client

COLORS = {
    "bg_app": "#1E1E1E",
    "bg_text_field": "#3C3C3C",
    "login_text": "#569CD6",
    "login_text_active": "#C56038",
    "base_button": "#0E639C",
    "base_button_active": "#1177BB",
    "button_text": "#FFFFFF",
    "entry_text": "#D4D4D4",
    "text_delete": "#FFFFFF",
    "text_delete_bg": "#F14C4C",
    "selection": "#264F78",
    "selection_txt": "#FFFFFF",
    "border": "#2D2D2D"
}

FONTS = {
    "base": ("Consolas", 15, "bold"),
    "thin_base": ("Consolas", 15),
    "small": ("Consolas", 12)
}

class CustomButton(tk.Button):
    def __init__(self, frame, **kwargs):
        super().__init__(
            frame,
            font=FONTS["base"],
            bg=COLORS["base_button"],
            fg=COLORS["button_text"],
            activebackground=COLORS["base_button_active"],
            activeforeground=COLORS["button_text"],
            relief="flat",
            bd=0,
            cursor="hand2"
        )
        self.config(kwargs)

class SeeThroughButton(tk.Button):
    def __init__(self, frame, bg_color, **kwargs):
        super().__init__(
            frame,
            font=FONTS["base"],
            bg=bg_color,
            bd=0,
            relief="flat",
            fg=COLORS["login_text"],
            activebackground=bg_color,
            activeforeground=COLORS["login_text_active"],
            cursor="hand2"
        )
        self.config(kwargs)

class WindowManager:
    def __init__(self):
        self.client = Client()

        self.window = tk.Tk()
        self.window.title("REDIS CHAT")
        self.window.geometry("600x500")
        self.window.configure(bg=COLORS["bg_app"])

        self.current_user: str = None
        self.current_chat: str = None
        self.current_action = None 

        self.main_container = tk.Frame(self.window, bg=COLORS["bg_app"])
        self.main_container.pack(fill="both", expand=True)

        #Frames
        self.login_frame = LoginFrame(self.main_container, self)
        self.menu_frame = MenuFrame(self.main_container, self)
        self.chat_frame = ChatFrame(self.main_container, self)

        self.login_frame.pack(fill="both", expand=True)

        self.window.after(100, self.run)
        self.window.mainloop()
       

    def run(self):
        try:
            while not self.client.server_responses.empty():
                success, data = self.client.get_response()
                if not success:
                    messagebox.showerror("Error", data.get("msg"))
                    continue
                self.handle_server_response(success, data)
        except Exception as e:
            print(f"Błąd odczytu odpowiedzi: {e}")

        try:
            while not self.client.notifications.empty():
                msg = self.client.get_notification()
                self.handle_notification(msg)
        except Exception as e:
            print(f"Błąd odczytu notyfikacji: {e}")

        self.window.after(100, self.run)

    def handle_server_response(self, success, data):
        action = data.get("action")
        msg = data.get("msg")

        if action == "login":
            self.load_Menu()
            
        elif action == "register":
            from tkinter import messagebox
            messagebox.showinfo("Success", "Account created successfully. You can now log in.")
        
        elif action == "get_users":
            self.menu_frame.update_user_list(msg)
            
        elif action == "get_chats":
            self.menu_frame.update_chat_list(msg)
            
        elif action == "chat_his":
            self.chat_frame.chat.config(state="normal")
            self.chat_frame.chat.delete("1.0", tk.END)
            for entry in reversed(msg):
                _, payload = entry
                sender = payload.get("user", "System")
                text = payload.get("message", "")
                self.chat_frame.chat.insert(tk.END, f"{sender}: {text}\n")
            self.chat_frame.chat.config(state="disabled")
            self.chat_frame.chat.see(tk.END)

        elif action == "get_members":
            self.chat_frame.members_list.delete(0, tk.END)
            for member in msg:
                self.chat_frame.members_list.insert(tk.END, member)

    def handle_notification(self, notif):
        notif_type = notif.get("type")
        
        if notif_type == "new_msg":
            if notif.get("chat") == self.current_chat:
                self.chat_frame.add_single_msg(notif.get("sender"), notif.get("text"))
                
        elif notif_type == "new_chat":
            self.client.send_chats_list_request()
            
        elif notif_type == "member_update":
            if notif.get("chat") == self.current_chat:
                self.chat_frame.add_single_msg("--", notif.get("text"))
                self.client.send_chat_members_list_request(self.current_chat)

    def load_Menu(self):
        self.swap_frame(self.menu_frame)
        self.client.send_user_list_request()
        self.client.send_chats_list_request()
        self.login_frame.clear_login_fields()

    def handle_msg(self, msg):
        if self.current_chat:
            self.client.send_msg_request(self.current_chat, msg)
            self.chat_frame.add_single_msg(self.current_user, msg)

    def handle_logout(self):
        self.current_user = None
        self.window.title("REDIS CHAT")
        self.client.disconnect()
        self.swap_frame(self.login_frame)
        
    def handle_del_account(self):
        if messagebox.askyesno("Confirmation", "Are you sure you want to delete your account?"):
            self.client.send_del_account_request("User requested deletion")
            self.client.disconnect()
            self.swap_frame(self.login_frame)

    def handle_add_member(self, member):
        if self.current_chat:
            self.client.send_add_to_chat_request(self.current_chat, member)

    def handle_del_from_chat(self, members):
        if self.current_chat:
            for member in members:
                self.client.send_del_from_chat_request(self.current_chat, member)

    def swap_frame(self, new_frame: tk.Frame):
        for frame in [self.login_frame, self.menu_frame, self.chat_frame]:
            frame.pack_forget()
        new_frame.pack(fill="both", expand=True)
    
    def ensure_connection(self, host: str, port: int) -> bool:
        if self.client.is_connected and self.client.host == host and self.client.port == port:
            return True
        
        self.client.disconnect()
        self.client.host = host
        self.client.port = port
        
        if self.client.connect():
            return True
        else:
            messagebox.showerror("Error", f"Could not connect to server {host}:{port}")
            return False

    def handle_login(self, host, port_str, username, password):
        try:
            port = int(port_str)
        except ValueError:
            messagebox.showerror("Error", "Port has to be an integer")
            return

        if not self.ensure_connection(host, port):
            return
            
        self.current_user = username
        self.window.title(f"REDIS CHAT: {username}")
        self.client.send_login_request(username, password)

    def handle_registration(self, host, port_str, username, password):
        try:
            port = int(port_str)
        except ValueError:
            messagebox.showerror("Error", "Port has to be an integer")
            return

        if not self.ensure_connection(host, port):
            return

        self.client.send_register_request(username, password)

    def handle_new_chat(self, chat_name, user_list=[]):
        self.client.send_new_chat_request(chat_name, user_list)
        self.menu_frame.clear_fields()
    
    def handle_chat_selection(self, chat_name):
        self.current_chat = chat_name
        self.chat_frame.set_chat_name(chat_name)
        self.swap_frame(self.chat_frame)
        self.client.send_chat_history_request(chat_name, "+", limit=50)
        self.client.send_chat_members_list_request(chat_name)
    
class LoginFrame(tk.Frame):
    def __init__(self, root, menager):
        self.menager = menager
        self.root = root
        super().__init__(root, bg=COLORS["bg_app"])
        center_frame = tk.Frame(self, background=COLORS["bg_app"])
        
        # Connection inputs
        self.host_input = tk.StringVar(value="localhost")
        self.port_input = tk.StringVar(value="50000")
        
        tk.Label(center_frame, text="IP Serwera:", bg=COLORS["bg_app"], fg=COLORS["login_text"], font=FONTS["small"]).pack(pady=(10, 0))
        host_frame = tk.Frame(center_frame, bg=COLORS["bg_text_field"], padx=6, pady=3)
        self.host_box = tk.Entry(host_frame, textvariable=self.host_input, font=FONTS["base"], width=16, fg=COLORS["login_text_active"], bg=COLORS["bg_text_field"], insertbackground="#FFFFFF", relief="flat", bd=0)
        self.host_box.pack()
        host_frame.pack(padx=5, pady=2)

        tk.Label(center_frame, text="Port Serwera:", bg=COLORS["bg_app"], fg=COLORS["login_text"], font=FONTS["small"]).pack(pady=(5, 0))
        port_frame = tk.Frame(center_frame, bg=COLORS["bg_text_field"], padx=6, pady=3)
        self.port_box = tk.Entry(port_frame, textvariable=self.port_input, font=FONTS["base"], width=16, fg=COLORS["login_text_active"], bg=COLORS["bg_text_field"], insertbackground="#FFFFFF", relief="flat", bd=0)
        self.port_box.pack()
        port_frame.pack(padx=5, pady=2)

        # Login inputs
        self.login_input = tk.StringVar()
        self.password_input = tk.StringVar()

        tk.Label(center_frame, text="Login:", bg=COLORS["bg_app"], fg=COLORS["login_text"], font=FONTS["small"]).pack(pady=(15, 0))
        login_box_frame = tk.Frame(center_frame, bg=COLORS["bg_text_field"], padx=6, pady=3)
        self.login_box = tk.Entry(login_box_frame, textvariable=self.login_input, font=FONTS["base"], width=16, fg=COLORS["login_text_active"], bg=COLORS["bg_text_field"], insertbackground="#FFFFFF", relief="flat", bd=0)
        self.login_box.pack()
        login_box_frame.pack(padx=5, pady=2)

        tk.Label(center_frame, text="Hasło:", bg=COLORS["bg_app"], fg=COLORS["login_text"], font=FONTS["small"]).pack(pady=(5, 0))
        pass_frame = tk.Frame(center_frame, bg=COLORS["bg_text_field"], padx=6, pady=3)
        self.password_box = tk.Entry(pass_frame, show="*", textvariable=self.password_input, font=FONTS["base"], width=16, fg=COLORS["login_text_active"], bg=COLORS["bg_text_field"], insertbackground="#FFFFFF", relief="flat", bd=0)        
        self.password_box.pack()
        pass_frame.pack(padx=5, pady=5)

        # Buttons
        login_func = lambda: menager.handle_login(self.host_input.get(), self.port_input.get(), self.login_input.get(), self.password_input.get())
        register_func = lambda: menager.handle_registration(self.host_input.get(), self.port_input.get(), self.login_input.get(), self.password_input.get())

        button_frame = tk.Frame(center_frame, background=COLORS["bg_app"])
        self.login_button = CustomButton(button_frame, text="login", command=login_func)
        self.password_button = CustomButton(button_frame, text="register", command=register_func)
        self.login_button.pack(side=tk.LEFT, padx=5)
        self.password_button.pack(padx=5)
        button_frame.pack(padx=5, pady=15)

        center_frame.pack(expand=True)

    def clear_login_fields(self):
        self.login_input.set("")
        self.password_input.set("")


class MenuFrame(tk.Frame):
    def __init__(self, root, menager):
        self.menager = menager
        self.root = root
        super().__init__(root, width=800, height=600, bg=COLORS["bg_app"])
        left_col_frame = tk.Frame(self, bg=COLORS["border"])
        right_col_frame = tk.Frame(self, bg=COLORS["bg_app"])

        # LEFT LIST
        self.users_list = tk.Listbox(
            left_col_frame,
            activestyle="none",
            selectforeground=COLORS["selection_txt"],
            selectbackground=COLORS["selection"],
            selectmode="multiple",
            font=FONTS["small"],
            background=COLORS["bg_text_field"],
            fg=COLORS["entry_text"],
            relief="flat",
            bd=0,
            highlightthickness=0
        )

        # LEFT CREATE
        chat_creator_frame = tk.Frame(left_col_frame, bg=COLORS["bg_app"])
        self.chat_name_input = tk.StringVar()
        new_chat_entry = tk.Entry(
            chat_creator_frame,
            textvariable=self.chat_name_input,font=FONTS["thin_base"],
            width=10,
            background=COLORS["bg_text_field"],
            fg=COLORS["entry_text"],
            insertbackground="#FFFFFF",
            relief="flat",
            bd=0
        )
     
        create_button = CustomButton(chat_creator_frame, font=FONTS["small"], text="create", command=self.create_new_chat)
        
        # LEFT LOGOUT AND ACCOUNT DEL
        logout_button = CustomButton(left_col_frame, font=FONTS["small"], text="logout", command=self.menager.handle_logout)
        del_account_button = SeeThroughButton(
            left_col_frame,
            bg_color=COLORS["border"],
            text="delete account",
            command=self.menager.handle_del_account,
            fg=COLORS["text_delete_bg"],
            activeforeground=COLORS["text_delete"],
            font=FONTS["small"]
            )
        
        # LEFT PACK
        new_chat_entry.pack(side=tk.LEFT, padx=5, pady=5)
        create_button.pack(padx=5, pady=5)
        chat_creator_frame.pack(padx=5, pady=5, fill="y")
        self.users_list.pack(expand=True, fill="both", padx=5, pady=5)
        logout_button.pack(fill="x", padx=5, pady=5)
        del_account_button.pack(fill="x", padx=5, pady=5)
        left_col_frame.pack(side=tk.LEFT, fill="y")

        # RIGHT
        self.chats_list = tk.Listbox(
            right_col_frame,
            activestyle="none",
            selectforeground=COLORS["selection_txt"],
            selectbackground=COLORS["selection"],
            font=FONTS["small"],
            background=COLORS["bg_text_field"],
            fg=COLORS["entry_text"],
            relief="flat",
            bd=0,
            highlightthickness=0
        )

        self.chats_list.bind("<<ListboxSelect>>", self.goto_chat)
        # RIGHT PACK
        self.chats_list.pack(expand=True, fill="both", padx=5, pady=5)
        right_col_frame.pack(expand=True, fill="both", padx=5, pady=5)

    def create_new_chat(self):
        users_list = []
        for i in self.users_list.curselection():
            user_name = self.users_list.get(i)
            users_list.append(user_name)
        self.menager.handle_new_chat(self.chat_name_input.get(), users_list)

    def update_user_list(self, users: list[str]):
        self.users_list.delete(0, tk.END)
        for user in users:
            if user != self.menager.current_user:
                self.users_list.insert(tk.END, user)
    
    def update_chat_list(self, chats: list[str]):
        self.chats_list.delete(0, tk.END)
        for chat in chats:
            self.chats_list.insert(tk.END, chat)

    def clear_fields(self):
        self.chat_name_input.set("")
        self.users_list.selection_clear(0, tk.END)        
        self.chats_list.selection_clear(0, tk.END)

    def goto_chat(self, event):
        selection = self.chats_list.curselection()
        if not selection:  
            return
        self.chats_list.selection_clear(0, tk.END)
        chat_name = self.chats_list.get(selection[0]) 
        self.menager.handle_chat_selection(chat_name)

class ChatFrame(tk.Frame):
    def __init__(self, root, menager):
        self.menager = menager
        self.root = root
        super().__init__(root, bg=COLORS["bg_app"])
        left_col_frame = tk.Frame(self, bg=COLORS["bg_app"])
        right_col_frame = tk.Frame(self, bg=COLORS["border"])

        # LEFT
        top_frame = tk.Frame(left_col_frame, bg=COLORS["bg_app"])

        back_button = SeeThroughButton(
            top_frame,
            bg_color=COLORS["bg_app"],
            text="< Back",
            fg=COLORS["login_text_active"],
            command=self.menager.load_Menu)
        
        self.chat_name_label = tk.Label(
            top_frame,
            text="Wybierz czat", 
            bg=COLORS["bg_app"],
            fg=COLORS["login_text"],
            font=FONTS["base"]
        )
        
        self.chat = tk.Text(
            left_col_frame,
            font=FONTS["small"],
            fg=COLORS["entry_text"],
            insertbackground="#FFFFFF",
            background=COLORS["bg_text_field"],
            state="disabled",
            relief="flat",
            bd=0,
            width=1
        )
        
        send_frame = tk.Frame(left_col_frame, bg=COLORS["bg_app"])

        self.user_msg_var = tk.StringVar()
        user_msg_entry = tk.Entry(
            send_frame,
            textvariable=self.user_msg_var,
            font=("Verdana", 15),
            background=COLORS["bg_text_field"],
            fg=COLORS["entry_text"],
            insertbackground="#FFFFFF",
            relief="flat",
            bd=0
        )
        
        user_msg_entry.bind("<Return>", self.send_msg)
        
        send_button = CustomButton(
            send_frame,
            text="Send",
            font=FONTS["small"],
            command=self.send_msg
            )
        
        # LEFT Pack
        back_button.pack(side=tk.LEFT, padx=5, pady=5)
        self.chat_name_label.pack(side=tk.LEFT, padx=5, pady=5)
        top_frame.pack(side=tk.TOP, fill="x")
        user_msg_entry.pack(side=tk.LEFT, expand=True, fill="x", padx=5, pady=5)
        send_button.pack(padx=5, pady=5)
        send_frame.pack(side=tk.BOTTOM, fill="x", padx=5, pady=5)
        self.chat.pack(expand=True, fill="both", padx=5, pady=5)
        
        # RIGHT
        members_label = tk.Label(
            right_col_frame,
            text="members:",
            bg=COLORS["border"],
            fg=COLORS["login_text_active"],
            font=FONTS["base"]
            )
        self.members_list = tk.Listbox(
            right_col_frame,
            activestyle="none",
            selectforeground=COLORS["text_delete"],
            selectbackground=COLORS["text_delete_bg"],
            font=FONTS["small"],
            selectmode="multiple",
            background=COLORS["bg_text_field"],
            width=20,
            fg=COLORS["entry_text"],
            relief="flat",
            bd=0,
            highlightthickness=0
            )
        
        del_user_button = tk.Button(
            right_col_frame,
            text="[ - ] remove member",
            fg=COLORS["text_delete_bg"],      # Czerwony tekst
            bg=COLORS["border"],              # Wtapia się w tło bocznego panelu
            activebackground=COLORS["text_delete_bg"],  # Czerwone tło po kliknięciu
            activeforeground="#FFFFFF",
            font=FONTS["small"],
            relief="flat",
            bd=0,
            cursor="hand2",
            pady=3,
            command=self.del_members
        )
        
        add_frame = tk.Frame(right_col_frame, bg=COLORS["border"])
        self.add_member_var = tk.StringVar(self)

        add_member_input = tk.Entry(
            add_frame,
            textvariable=self.add_member_var,
            font=FONTS["base"],
            background=COLORS["bg_text_field"],
            fg=COLORS["entry_text"],
            width=11
            )
        
        add_member_button = CustomButton(
            add_frame,
            text="+",
            font=FONTS["small"],
            command=self.add_member
            )

        # RIGHT PACK
        members_label.pack(padx=5, pady=5)
        self.members_list.pack(expand=True, fill="y", padx=5, pady=5)
        del_user_button.pack(fill="x", padx=8, pady=5)
        add_member_input.pack(side=tk.LEFT, fill="x", padx=5, pady=5)
        add_member_button.pack(pady=5)
        add_frame.pack(fill="x", padx=5, pady=5)

        right_col_frame.pack(side=tk.RIGHT, fill="y")
        left_col_frame.pack(side=tk.LEFT, fill="both", expand=True)

    def update(self, chat_log, membres_list):
        self.chat.delete("1.0", "end")
        self.chat.insert("end", chat_log)
        self.members_list.delete("1.0", "end")
        self.members_list.insert("end", *membres_list)

    def del_members(self):
        selected = self.members_list.curselection()
        names_list = []
        for i in reversed(selected):
            names_list.append(self.members_list.get(i))
            self.members_list.delete(i)
        self.menager.handle_del_from_chat(names_list)

    def add_member(self):
        member = self.add_member_var.get().strip()
        if member:
            self.add_member_var.set("")
            self.menager.handle_add_member(member)

    def send_msg(self, event=None):
        msg = self.user_msg_var.get().strip()
        if msg:
            self.user_msg_var.set("")
            self.menager.handle_msg(msg)
    
    def add_single_msg(self, sender, text):
        self.chat.config(state="normal")
        self.chat.insert(tk.END, f"{sender}: {text}\n")
        self.chat.config(state="disabled")
        self.chat.see(tk.END)

    def set_chat_name(self, name):
        self.chat_name_label.config(text=name)

if __name__ == "__main__":
    wm = WindowManager()