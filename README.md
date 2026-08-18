# Aplikacja czatu w czasie rzeczywistym

**dane techniczne:**
Język programowania : Python
Komunikacja: TCP
Baza Danych: Redis
Zapis chatu: Redis Streams


## Funkcjonalności  

### Logowanie  
>Na ekranie logowania użytkownik podaje login i hasło.
hasło nie jest widoczne podczas wpisywania.
po zalogowaniu login jest widoczny w tytule okna.

### Rejestracja
>Ma miejsce w tych samych rubrykach co logowanie.
po lejestracji użytkownik zostaje automatycznie zalogowany i zapisany w bazie.

### Tworzenie chatu
>By utworzyć nowy chat należy zaznaczyć jego przyszłych członków wpisać nazwę chatu w odpowiedniej rubryce i zatwierdzić operację.

### Dodawanie nowych członków do chatu
>By dodać nowego członka do konwersacji należy podaćjego login. Jeśli użytkownik o takim nicku istnieje zostaje powiadomoiny i dodany do chatu. 

### Wysyłanie wiadomości na chatach grupowych
>Użytkownicy mogą wysyłać wiadomości na chacie i widzieć je w czasie rzeczywistym. by wysłać wiadomość należy wcisnąć przycisk na dole ekranu lub klawisz enter.

### Możliwość usunięcia członka chatu
>Użytkownicy chaty mogą usunąć członków z konwersacji. po usunięciu ostatniego członka konwersacja zostaje usunięta z bazy danych.

### Możliwość usunięcia konta
>Istnieje możliwość usunięcia własnego konta. w takim wypadku znikamy z listy użytkowników. Wysłane przez nas wiadomości nadal pozostają na chacie. 

## Baza danych
Redis jako baza danych świetnie sprawdza się przy projektach tego typu.
Jest prosty w implementacji a struktóra stream świetnie sprawdza się w przechowywaniu logów chatu.
Dodatkowo strumienie pozwalają na odczyt fragmentów konwersacji w oparciu o ramy czasowe lub id wiadomości.

struktóra bazy w tym projekcie prezentuje się zastępująco 

 **Users:**

     user:id_counter (String) –  ID counter.

     users:by_name (Hash) – Key: name, Value: id.

     user:{id}:credentials (Hash) – Login: xyz, Password: ***.

     user:{id}:chats (Set) – chats ID-s.

     users:all (Set) – Users ID set.

 **Chats:**

     chat:id_counter (String) – ID counter.

     chats:by_name (Hash) – Key: name, Value: id.
     chats:by_id (Hash) – Key: id, Value: name.

     chat:{id}:members (Set) – ID-s of chat members.

     chat:{id}:messages (Stream) – chat log.

## Wygląd aplikacji
![Ekran logowania](login_window.png)
![Okno główne](main_window.png)
![Okno chatu](chat_window.png)
