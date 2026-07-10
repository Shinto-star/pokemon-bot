import os
import requests
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from flask import Flask

app = Flask(__name__)

# Hier kannst du beliebig viele Links mit einem Komma getrennt eintragen
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
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                viewport={"width": 1920, "height": 1080}
            )
            
            current_products = {}
            
            # Beide Links nacheinander scannen
            for current_url in URLS:
                page = context.new_page()
                page.goto(current_url, wait_until="networkidle", timeout=60000)
                html = page.content()
                page.close()
                
                soup = BeautifulSoup(html, 'html.parser')
                products = soup.find_all('div', class_='product-card') 
                
                for prod in products:
                    title_elem = prod.find('p', class_='product-title') 
                    status_elem = prod.find('span', class_='out-of-stock') 
                    if title_elem:
                        title = title_elem.text.strip()
                        # Speichert Titel, Verfügbarkeit UND den dazugehörigen Link
                        current_products[title] = {
                            "available": not bool(status_elem),
                            "link": current_url
                        }
            
            browser.close()

            # Erste Ausführung: Alle gefundenen Produkte von beiden Seiten abspeichern
            if not known_products:
                known_products = set(current_products.keys())
                return f"Erster Check fertig. {len(known_products)} Produkte auf beiden Seiten gefunden."

            # Ab dem zweiten Lauf: Prüfen, was neu dazugekommen ist
            for title, data in current_products.items():
                if title not in known_products:
                    known_products.add(title)
                    if data["available"]:
                        send_telegram_notification(f"🚨 NEUES PRODUKT:\n{title}\n\nLink: {data['link']}")
                        new_alerts += 1
                
            return f"5-Minuten-Check abgeschlossen. {new_alerts} neue Produkte gefunden."
            
    except Exception as e:
        return f"Fehler aufgetreten: {e}"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
