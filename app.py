import os
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

@app.route('/')
def check_site():
    global known_products
    try:
        new_alerts = 0
        
        with sync_playwright() as p:
            # SPEICHER-OPTIMIERUNG 1: Chrome im absoluten Minimal-Modus starten
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu'
                ]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                viewport={"width": 1920, "height": 1080}
            )
            
            current_products = {}
            
            for current_url in URLS:
                page = context.new_page()
                
                # SPEICHER-OPTIMIERUNG 2: Alle Bilder, Videos und Schriftarten blockieren!
                page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font"] else route.continue_())
                
                page.goto(current_url, wait_until="networkidle", timeout=60000)
                html = page.content()
                page.close() # Tab sofort schließen, um Speicher freizugeben
                
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
            
            browser.close()

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
