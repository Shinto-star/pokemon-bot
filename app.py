import os
import gc
import requests
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
    """Startet Chrome, holt den reinen Text und schließt Chrome sofort wieder, um RAM zu sparen."""
    html = ""
    with sync_playwright() as p:
        # EXTREM-DIÄT für Chromium
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--single-process',
                '--no-zygote'
            ]
        )
        # Sehr kleines Fenster simulieren
        context = browser.new_context(viewport={"width": 800, "height": 600})
        page = context.new_page()
        
        # Blockiere ALLES außer reinem HTML und Skripten (auch CSS wird geblockt)
        page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font", "stylesheet"] else route.continue_())
        
        try:
            # "domcontentloaded" ist schneller als "networkidle" und spart Speicher
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            html = page.content()
        except Exception as e:
            print(f"Fehler beim Laden von {url}: {e}")
        finally:
            browser.close() # Browser SOFORT killen!
            
    return html

@app.route('/')
def check_site():
    global known_products
    new_alerts = 0
    current_products = {}
    
    try:
        # Jeden Link EINZELN abarbeiten
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
            
            # Python zwingen, den RAM SOFORT wieder freizugeben
            gc.collect()

        if not known_products:
            known_products = set(current_products.keys())
            return f"Erster Check fertig. {len(known_products)} Produkte gefunden."

        for title, data in current_products.items():
            if title not in known_products:
                known_products.add(title)
                if data["available"]:
                    send_telegram_notification(f"🚨 NEUES PRODUKT:\n{title}\n\nLink: {data['link']}")
                    new_alerts += 1
            
        return f"Check abgeschlossen. {new_alerts} neue Produkte gefunden."
        
    except Exception as e:
        return f"Fehler aufgetreten: {e}"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
