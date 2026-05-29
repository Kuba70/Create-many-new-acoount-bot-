"""
TempMail Bot — szkielet
========================
Przepływ:
  1. Otwórz temp-mail.org → pobierz tymczasowy adres email
  2. Przejdź na stronę rejestracji → wypełnij email + losowe hasło → wyślij formularz
  3. Wróć na temp-mail.org → czekaj na email potwierdzający

Zależności:
  pip install playwright
  playwright install chromium
"""

import asyncio
import random
import string
import time

from playwright.async_api import async_playwright, Page, Browser

from config import (
    REGISTRATION_URL,
    SELECTORS,
    PASSWORD_LENGTH,
    PASSWORD_USE_SPECIAL,
    WAIT_FOR_EMAIL_TIMEOUT_SEC,
    WAIT_FOR_EMAIL_POLL_SEC,
    HEADLESS,
    SLOW_MO,
    ITERATIONS,
)

# ─────────────────────────────────────────────
#  POMOCNICZE FUNKCJE
# ─────────────────────────────────────────────

def generate_password(length: int = 12, use_special: bool = True) -> str:
    """Generuje losowe hasło spełniające typowe wymagania."""
    chars = string.ascii_letters + string.digits
    if use_special:
        chars += "!@#$%^&*"
    # Gwarantuj co najmniej 1 cyfrę, 1 wielką literę, 1 małą literę
    password = [
        random.choice(string.ascii_uppercase),
        random.choice(string.ascii_lowercase),
        random.choice(string.digits),
    ]
    if use_special:
        password.append(random.choice("!@#$%^&*"))
    password += random.choices(chars, k=length - len(password))
    random.shuffle(password)
    return "".join(password)


# ─────────────────────────────────────────────
#  KROK 1 — Pobierz email z temp-mail.org
# ─────────────────────────────────────────────

async def get_temp_email(page: Page) -> str:
    """
    Otwiera temp-mail.org i zwraca wygenerowany adres email.
    """
    print("[1/3] Otwieram temp-mail.org …")
    await page.goto("https://temp-mail.org/", wait_until="domcontentloaded")

    # temp-mail.org wczytuje adres dynamicznie — czekamy aż pole będzie wypełnione
    email_input = page.locator("#mail")
    await email_input.wait_for(state="attached", timeout=30_000)

    # Poczekaj aż pole nie będzie puste
    for _ in range(20):
        email = await email_input.input_value()
        # Zabezpieczenie: jeśli to div/span, użyjemy inner_text
        if not email:
            email = await email_input.inner_text()
            
        if email and "@" in email:
            print(f"    ✓ Adres email: {email}")
            return email.strip()
        await asyncio.sleep(1)

    raise RuntimeError("Nie udało się pobrać adresu email z temp-mail.org")


# ─────────────────────────────────────────────
#  KROK 2 — Rejestracja na docelowej stronie
# ─────────────────────────────────────────────

async def register_account(page: Page, email: str, password: str) -> None:
    """
    Przechodzi na stronę rejestracji i wypełnia formularz.
    """
    print(f"[2/3] Otwieram stronę rejestracji: {REGISTRATION_URL}")
    await page.goto(REGISTRATION_URL, wait_until="domcontentloaded")

    # --- Opcjonalnie: akceptacja cookies ---
    print("    › Sprawdzam czy jest banner z plikami cookies...")
    cookie_selectors = [
        "button:has-text('Akceptuj')", "button:has-text('Zgadzam się')", 
        "text='Akceptuję'", "text='Zgadzam się'", "button:has-text('Zaakceptuj')",
        "#onetrust-accept-btn-handler", ".cookie-accept", ".accept-cookies"
    ]
    await asyncio.sleep(2) # Dajmy chwilę na animację bannera
    for sel in cookie_selectors:
        try:
            loc = page.locator(sel).first
            if await loc.is_visible():
                await loc.click(force=True)
                print(f"      ✓ Kliknięto zgody na cookies ({sel}).")
                await asyncio.sleep(1)
                break
        except Exception:
            pass

    # --- Pole email ---
    email_sel = SELECTORS["email_field"]
    print(f"    › Wpisuję email w: {email_sel}")
    await page.locator(email_sel).wait_for(state="visible", timeout=15_000)
    await page.locator(email_sel).fill(email)

    # --- Pole hasło ---
    pass_sel = SELECTORS["password_field"]
    print(f"    › Wpisuję hasło w: {pass_sel}")
    await page.locator(pass_sel).wait_for(state="visible", timeout=10_000)
    await page.locator(pass_sel).fill(password)

    # --- Pole "potwierdź hasło" (opcjonalne) ---
    confirm_sel = SELECTORS.get("confirm_password_field")
    if confirm_sel:
        print(f"    › Potwierdzam hasło w: {confirm_sel}")
        await page.locator(confirm_sel).wait_for(state="visible", timeout=10_000)
        await page.locator(confirm_sel).fill(password)

    # --- Checkboxy / Przełączniki (np. regulamin, zgody) ---
    checkboxes = SELECTORS.get("checkboxes", [])
    for idx, checkbox_sel in enumerate(checkboxes, start=1):
        print(f"    › Zaznaczam przełącznik/checkbox {idx}: {checkbox_sel}")
        loc = page.locator(checkbox_sel)
        await loc.wait_for(state="attached", timeout=5_000)
        # Używamy JavaScript do kliknięcia, to w 100% omija problemy Playwrighta 
        # z nakładającymi się divami i "niewidzialnymi" obszarami klikalnymi w Vue
        await loc.evaluate("el => el.click()")
        await asyncio.sleep(0.5)

    # --- Przycisk submit ---
    submit_sel = SELECTORS["submit_button"]
    print(f"    › Klikam przycisk: {submit_sel}")
    await page.locator(submit_sel).wait_for(state="visible", timeout=10_000)
    await page.locator(submit_sel).click()

    # Poczekaj chwilę aż strona zareaguje na kliknięcie
    await asyncio.sleep(3)
    print("    ✓ Formularz wysłany!")


# ─────────────────────────────────────────────
#  KROK 3 — Czekaj na email w temp-mail.org
# ─────────────────────────────────────────────

async def wait_for_confirmation_email(page: Page) -> Page | None:
    """
    Wraca na temp-mail.org i oczekuje na maila "Procedura aktywacji konta".
    Klika w maila, a następnie w przycisk "Aktywuj konto".
    Zwraca nową kartę (Page) ze stroną aktywacji.
    """
    print(f"[3/3] Wracam na temp-mail.org — oczekuję na email (max {WAIT_FOR_EMAIL_TIMEOUT_SEC}s) …")
    await page.goto("https://temp-mail.org/", wait_until="domcontentloaded")

    deadline = time.time() + WAIT_FOR_EMAIL_TIMEOUT_SEC
    attempt  = 0

    while time.time() < deadline:
        attempt += 1
        print(f"    Próba {attempt} — sprawdzam skrzynkę …")

        # Odśwież listę wiadomości jeśli jest taki przycisk
        try:
            refresh_btn = page.locator("#refresh, .refresh-button")
            if await refresh_btn.is_visible():
                await refresh_btn.click()
                await asyncio.sleep(2)
        except Exception:
            pass  

        # Szukamy po tytule/treści lub wierszach
        activation_mail = page.locator("text='Procedura aktywacji konta'")
        
        if await activation_mail.count() > 0:
            print(f"    ✓ Email 'Procedura aktywacji konta' otrzymany!")
            # Wymuszamy kliknięcie przez JS (często na temp-mail wyskakują reklamy blokujące klik)
            await activation_mail.first.evaluate("el => { let link = el.closest('a'); if(link) link.click(); else el.click(); }")
            await asyncio.sleep(4)
            print("    ✓ Wiadomość otwarta.")
            
            print("    › Szukam przycisku 'Aktywuj konto'...")
            
            # W temp-mail czasami treść maila jest w iframe, sprawdzamy też główny dokument
            btn = None
            async def get_btn():
                if await page.locator("text='Aktywuj konto'").count() > 0:
                    return page.locator("text='Aktywuj konto'").first
                for frame in page.frames:
                    if await frame.locator("text='Aktywuj konto'").count() > 0:
                        return frame.locator("text='Aktywuj konto'").first
                return None
            
            for _ in range(10):
                btn = await get_btn()
                if btn: break
                await asyncio.sleep(1)

            if not btn:
                print("    ✗ Nie znaleziono przycisku 'Aktywuj konto' w mailu.")
                return None

            print("    › Wyciągam link aktywacyjny 'Aktywuj konto'...")
            try:
                # Zamiast klikać (co może otworzyć reklamę), pobieramy atrybut href
                href = await btn.get_attribute("href")
                if href:
                    print(f"    ✓ Znaleziono link: {href}")
                    activation_page = await page.context.new_page()
                    # Aplikujemy stealth, żeby uniknąć bana
                    try:
                        from playwright_stealth import Stealth
                        await Stealth().apply_stealth_async(activation_page)
                    except ImportError:
                        pass
                        
                    await activation_page.goto(href, wait_until="domcontentloaded")
                    print("    › (Zabezpieczenie) Przeładowuję stronę, by uniknąć lagów Vue...")
                    await asyncio.sleep(2)
                    await activation_page.reload(wait_until="domcontentloaded")
                    print("    ✓ Strona aktywacyjna otwarta!")
                    return activation_page
                else:
                    print("    ✗ Przycisk 'Aktywuj konto' nie ma atrybutu href! Próbuję kliknąć...")
                    async with page.context.expect_page(timeout=10000) as new_page_info:
                        await btn.click(force=True)
                    activation_page = await new_page_info.value
                    await activation_page.wait_for_load_state("domcontentloaded")
                    print("    › (Zabezpieczenie) Przeładowuję stronę, by uniknąć lagów Vue...")
                    await asyncio.sleep(2)
                    await activation_page.reload(wait_until="domcontentloaded")
                    return activation_page
            except Exception as e:
                print(f"    › (Nie udało się otworzyć w nowej karcie: {e} - działam na obecnej)")
                await btn.click(force=True)
                await page.wait_for_load_state("domcontentloaded")
                await asyncio.sleep(2)
                await page.reload(wait_until="domcontentloaded")
                return page

        remaining = int(deadline - time.time())
        print(f"      Brak wiadomości. Następna próba za {WAIT_FOR_EMAIL_POLL_SEC}s "
              f"(pozostało ~{remaining}s) …")
        await asyncio.sleep(WAIT_FOR_EMAIL_POLL_SEC)

    print("    ✗ Timeout — email nie nadszedł w wyznaczonym czasie.")
    return None

# ─────────────────────────────────────────────
#  KROK 4 — Wypełnienie profilu
# ─────────────────────────────────────────────

async def fill_profile(page: Page) -> None:
    print("[4/4] Wypełniam profil na stronie aktywacji …")
    
    print("    › Czekam chwilę na ewentualny popup 'Włącz powiadomienia'...")
    await asyncio.sleep(3)
    try:
        # Szukamy typowych przycisków odrzucających powiadomienia/newslettery
        popup_btn = page.locator("button:has-text('Nie, dziękuję'), button:has-text('Nie teraz'), button:has-text('Później'), button:has-text('Zablokuj'), text='Później', text='Nie teraz'").first
        if await popup_btn.is_visible():
            await popup_btn.click(force=True)
            print("      ✓ Zamknięto popup.")
    except Exception:
        pass

    # 1. name (imię losowe)
    random_name = ''.join(random.choices(string.ascii_lowercase, k=8)).capitalize()
    print(f"    › Wpisuję imię: {random_name}")
    await page.locator("#name").wait_for(state="attached", timeout=15000)
    await page.locator("#name").fill(random_name)
    
    # 2. sex (płeć)
    print("    › Wybieram płeć...")
    sex_select = page.locator("#sex")
    try:
        # Próbujemy wybrać opcję nr 2 (index 1 lub 2 zależnie od tego czy index 0 to placeholder)
        await sex_select.select_option(index=random.choice([1, 2]))
    except Exception:
        # Fallback jeśli to nie jest natywny select
        await sex_select.click(force=True)
        await asyncio.sleep(0.5)
        await sex_select.press("ArrowDown")
        await sex_select.press("Enter")

    # 3. phone (9 cyfr zaczynających się od 5)
    phone = "5" + "".join(random.choices(string.digits, k=8))
    print(f"    › Wpisuję telefon: {phone}")
    await page.locator("#phone").fill(phone)

    # 4. wiek
    age_texts = ["< 24 lat", "25-34", "35-44", "45-55", "> 55 lat"]
    random_age = random.choice(age_texts)
    print(f"    › Zaznaczam wiek: {random_age}")
    try:
        age_loc = page.locator(f"text='{random_age}'").first
        await age_loc.evaluate("el => el.click()")
    except Exception:
        await page.locator(f"text='{random_age}'").first.click(force=True)

    # 5. przycisk zapisz zmiany
    print("    › Klikam 'Zapisz zmiany'...")
    save_btn = page.locator("text='Zapisz zmiany'").first
    await save_btn.evaluate("el => el.click()")
    
    print("    › Czekam na przeładowanie strony po zapisie...")
    await asyncio.sleep(5)
    print("    ✓ Zmiany zapisane!")
    
    # 6. Wejście w kartę i screenshot
    print("    › Wchodzę w 'Moja karta' i robię zdjęcie...")
    # Klikamy avatar w prawym górnym rogu, jeśli uda się go zlokalizować (różne warianty klas)
    avatar = page.locator(".m-topbar__user-profile, .m-nav__link-icon, img[src*='avatar'], .fa-user").first
    try:
        if await avatar.is_visible(timeout=2000):
            await avatar.click(force=True)
            await asyncio.sleep(1)
    except Exception:
        pass

    # Klikamy "Moja karta" przez JS, żeby zadziałało nawet gdyby menu nie zjechało
    moja_karta_btn = page.locator("text='Moja karta'").first
    await moja_karta_btn.wait_for(state="attached", timeout=10000)
    await moja_karta_btn.evaluate("el => el.click()")
    
    # Czekamy aż popup z kodem kreskowym się załaduje
    await asyncio.sleep(4)
    
    # Zapis screena do pliku
    import os
    screenshot_name = f"moja_karta_{int(time.time())}.png"
    filepath = os.path.join(os.getcwd(), screenshot_name)
    await page.screenshot(path=filepath, full_page=True)
    print(f"    ✓ Zrzut ekranu zapisany jako: {screenshot_name}")
    
    # 7. Wylogowanie, by kolejna iteracja miała czyste środowisko
    print("    › Wylogowuję z konta (aby nie psuć kolejnej iteracji)...")
    try:
        # Kliknij w avatar jeszcze raz, by upewnić się że menu jest rozsunięte
        if await avatar.is_visible(timeout=2000):
            await avatar.click(force=True)
            await asyncio.sleep(1)
            
        logout_btn = page.locator("a:has-text('Wyloguj'), a.m-btn--label-info").first
        await logout_btn.evaluate("el => el.click()")
        await asyncio.sleep(3)
        print("    ✓ Wylogowano pomyślnie.")
    except Exception as e:
        print(f"    ✗ Nie udało się wylogować: {e}")
        # Awaryjnie wyczyść LocalStorage z poziomu przeglądarki
        await page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); document.cookie.split(';').forEach(function(c) { document.cookie = c.replace(/^ +/, '').replace(/=.*/, '=;expires=' + new Date().toUTCString() + ';path=/'); }); }")


# ─────────────────────────────────────────────
#  GŁÓWNA FUNKCJA
# ─────────────────────────────────────────────

async def run_bot() -> None:
    print("=" * 50)
    print("  TempMail Registration Bot")
    print("=" * 50)

    async with async_playwright() as pw:
        browser: Browser = await pw.chromium.launch(
            headless=HEADLESS,
            slow_mo=SLOW_MO,
        )
        context = await browser.new_context()
        
        # Zakładka 1: 10minutemail / temp-mail
        mail_page = await context.new_page()

        # Ukrywanie automatyzacji za pomocą stealth pluginu
        try:
            from playwright_stealth import Stealth
            await Stealth().apply_stealth_async(mail_page)
            print("  [Stealth] Moduł anty-detekcji aktywowany (API v2).")
        except ImportError:
            try:
                from playwright_stealth import stealth_async
                await stealth_async(mail_page)
                print("  [Stealth] Moduł anty-detekcji aktywowany (API v1).")
            except ImportError:
                print("  [Stealth] OSTRZEŻENIE: Nie można zainicjować playwright-stealth.")

        # Pętla generująca konta
        for i in range(1, ITERATIONS + 1):
            print(f"\n{'=' * 50}")
            print(f"  ROZPOCZYNAM ITERACJĘ {i} z {ITERATIONS}")
            print("=" * 50)
            
            password = generate_password(PASSWORD_LENGTH, PASSWORD_USE_SPECIAL)
            print(f"  Hasło do rejestracji: {password}\n")

            reg_page = None
            try:
                # Krok 1 — pobierz email
                email = await get_temp_email(mail_page)

                # Zakładka 2: Rejestracja
                reg_page = await context.new_page()
                try:
                    from playwright_stealth import Stealth
                    await Stealth().apply_stealth_async(reg_page)
                except ImportError:
                    pass

                # Krok 2 — zarejestruj konto
                await register_account(reg_page, email, password)

                # Krok 3 — czekaj na email (wracamy do pierwszej zakładki)
                await mail_page.bring_to_front()
                activation_page = await wait_for_confirmation_email(mail_page)

                # Krok 4 - wypełnij profil
                if activation_page:
                    await fill_profile(activation_page)
                    # Zamknij kartę aktywacyjną
                    if activation_page != mail_page:
                        await activation_page.close()
                    
                print("\n" + "=" * 50)
                if activation_page:
                    print(f"  ITERACJA {i} ZAKOŃCZONA POMYŚLNIE ✓")
                    print(f"  Email:  {email}")
                    print(f"  Hasło:  {password}")
                else:
                    print(f"  ITERACJA {i} ZAKOŃCZONA BŁĘDEM (Brak maila) ✗")
                print("=" * 50)

            except Exception as exc:
                print(f"\n[BŁĄD W ITERACJI {i}] {exc}")
                
            finally:
                # Zamykamy kartę rejestracji, jeśli powstała
                if reg_page and not reg_page.is_closed():
                    await reg_page.close()

                if i < ITERATIONS:
                    print("\n    › Klikam przycisk Usuń (Delete), by wygenerować nowy adres e-mail...")
                    await mail_page.bring_to_front()
                    try:
                        delete_btn = mail_page.locator("#click-to-delete, .delete-button").first
                        await delete_btn.click(force=True)
                        await asyncio.sleep(5)
                    except Exception as e:
                        print(f"      (Nie udało się usunąć maila: {e})")
                        await mail_page.reload()
                        await asyncio.sleep(3)

        # Na koniec, poza pętlą
        print("\nWszystkie iteracje zakończone. Zamykam przeglądarkę za 10s...")
        await asyncio.sleep(10)
        await context.close()
        await browser.close()


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    asyncio.run(run_bot())
