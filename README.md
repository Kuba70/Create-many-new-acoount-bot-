# TempMail Registration Bot

Automatyczny bot do rejestracji konta z użyciem tymczasowego adresu email.

## Instalacja

```powershell
pip install -r requirements.txt
playwright install chromium
```

## Konfiguracja (przed uruchomieniem!)

Otwórz **`config.py`** i uzupełnij:

| Pole | Opis |
|------|------|
| `REGISTRATION_URL` | Adres Twojej lokalnej strony rejestracji |
| `SELECTORS["email_field"]` | Selektor CSS/id pola email |
| `SELECTORS["password_field"]` | Selektor CSS/id pola hasła |
| `SELECTORS["confirm_password_field"]` | Selektor pola "potwierdź hasło" (lub `None`) |
| `SELECTORS["submit_button"]` | Selektor przycisku submit |

### Jak znaleźć selektory?
1. Otwórz swoją stronę w Chrome/Edge
2. Kliknij prawym przyciskiem na pole → **Zbadaj (Inspect)**
3. Znajdź atrybut `id` lub `name` elementu, np. `id="email"` → selektor: `#email`

## Uruchomienie

```powershell
python bot.py
```

## Przepływ działania

```
temp-mail.org          Twoja strona               temp-mail.org
     │                      │                          │
     ▼                      │                          │
Pobierz email ──────────────▶                          │
                       Wpisz email + hasło             │
                       Kliknij "Zarejestruj" ──────────▶
                                                  Czekaj na
                                                  email potwier-
                                                  dzający (polling)
```

## Struktura plików

```
tempmail-bot/
├── bot.py          ← główny skrypt (logika bota)
├── config.py       ← TUTAJ wpisujesz swoje ustawienia
├── requirements.txt
└── README.md
```
