import os
import gc
import requests
import threading
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from flask import Flask

app = Flask(__name__)

URLS = [
    "https://www.pokemoncenter.com/en-de/category/trading-card-game?category=tcg-cards",
    "https://www.pokemoncenter.com/en-gb/category/elite-trainer-box"
]

TELEGRAM_TOKEN = "8881297286:AAFeVrIp1vPmMie4PDKV_CvsamGVuQ1eWZ8"
TELEGRAM_CHAT_ID = "820268921"
known_products = set()

def send_telegram_notification(message):
    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(telegram_url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message})

def fetch_page_html(url):
    html = ""
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu'
            ]
        )
        context = browser.new_context(viewport={"width": 800, "height": 600})
        page = context.new_page()
        page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font", "stylesheet"] else route.continue_())
        
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            # --- UNSER NEUER SPION ---
            print(f"[*] Erfolgreich geladen! Der Titel der Seite lautet: '{page.title()}'")
            # -------------------------
            
            html = page.content()
        except Exception as e:
            print(f"Fehler beim Laden von {url}: {e}")
        finally:
            browser.close()
            
    return html

def run_scan():
    global known_products
    current_products = {}
    
    try:
        print("[*] Starte neuen Suchlauf...")
        for current_url in URLS:
            html = fetch_page_html(current_url)
            if not html:
                continue
                
            soup = BeautifulSoup(html, 'html.parser')
            products = soup.find_all('div', class_='product-card') 
            
            for prod in products:
                title_elem = prod.find('p', class_='product-title') 
                status_elem = prod.find('span', class_='out-of-stock') 
                if title_elem:
                    title = title_elem.text.strip()
                    current_products[title] = {
                        "available": not bool(status_elem),
                        "link": current_url
                    }
            gc.collect()

        if not known_products:
            known_products = set(current_products.keys())
            print(f"Initialisierung: {len(known_products)} Produkte gefunden.")
            return

        for title, data in current_products.items():
            if title not in known_products:
                known_products.add(title)
                if data["available"]:
                    send_telegram_notification(f"🚨 NEUES PRODUKT:\n{title}\n\nLink: {data['link']}")
                    
    except Exception as e:
        print(f"Fehler im Hintergrund-Scan: {e}")

@app.route('/')
def trigger_scan():
    thread = threading.Thread(target=run_scan)
    thread.start()
    return "Scan im Hintergrund erfolgreich gestartet!", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
