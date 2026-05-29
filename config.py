# =============================================================================
#  KONFIGURACJA BOTA — uzupełnij poniższe wartości przed uruchomieniem
# =============================================================================

# --- Twoja lokalna strona rejestracji ---
REGISTRATION_URL = "https://app.lowokazje.pl/sign-up"  # <-- zmień na swój adres

# --- Selektory pól formularza rejestracji ---
# Sprawdź je w DevTools przeglądarki (F12 → Inspector)
SELECTORS = {
    "email_field":    "#m_email",          # <-- selektor pola email
    "password_field": ":nth-match(input[type=\"password\"], 1)",       # <-- selektor pola hasło (pierwsze na stronie)
    "confirm_password_field": ":nth-match(input[type=\"password\"], 2)",      # <-- selektor potwierdzenia hasła (drugie na stronie)
    "checkboxes":     [                  # <-- wpisz selektory checkboxów/przełączników (np. regulamin)
        ":nth-match(label.vue-switcher, 1)",
        ":nth-match(label.vue-switcher, 2)"
    ],
    "submit_button":  "#m_login_forget_password_submit",         # <-- selektor przycisku "Zarejestruj"
}

# --- Ustawienia hasła ---
PASSWORD_LENGTH = 12          # długość losowego hasła
PASSWORD_USE_SPECIAL = True   # czy używać znaków specjalnych (!@#$...)

# --- Oczekiwanie na email potwierdzający ---
WAIT_FOR_EMAIL_TIMEOUT_SEC = 120   # ile sekund czekać łącznie na email
WAIT_FOR_EMAIL_POLL_SEC    = 5     # co ile sekund sprawdzać skrzynkę

# --- Ustawienia ogólne ---
ITERATIONS = 4                     # <-- ile razy bot ma powtórzyć proces (ile kont założyć)
HEADLESS = False   # False = widzisz okno przeglądarki; True = działa w tle
SLOW_MO  = 190    # opóźnienie między akcjami (ms) — 0 = max prędkość
