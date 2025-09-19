from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
import time
import os, csv
from datetime import datetime

class CSGOEmpireScraper:
    def __init__(self):
        self.url = "https://csgoempire.com/"
        self.playwright = None
        self.browser = None
        self.page = None

    def open_page(self):
        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(
                headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"]
            )
            self.page = self.browser.new_page()
            self.page.goto(self.url, wait_until="domcontentloaded")
            title = self.page.title()
            print(f"Opened Website: {title}")
        except Exception as e:
            print(f"Exception: {e}")
            self.close()

    def close(self):
        if self.page:
            self.page.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def track_roulette(self, polling_rate=3):
        self.open_page()
        ensure_csv()
        last_ten_rolls = self.read_rolls()

        while True:
            time.sleep(polling_rate)
            try:
                new_ten_rolls = self.read_rolls()
                if last_ten_rolls == new_ten_rolls:
                    continue
                else:
                    check = True
                    for i in range(1, len(new_ten_rolls) - 1):
                        if new_ten_rolls[i-1] != last_ten_rolls[i]:
                            check = False

                    if not check:
                        print("Something went wrong. Reloading...")
                        continue
                    else:
                        # add new_ten_rolls[len(new_ten_rolls - 1] to csv
                        new_item = new_ten_rolls[-1]
                        now = datetime.now().strftime("%H:%M")
                        with open("rolls.csv", "a", newline="") as f:
                            writer = csv.writer(f)
                            writer.writerow([now, new_item])
                        print(f"New roll found: {new_item}, at: {now}")

                        last_ten_rolls = new_ten_rolls
            except Exception as e:
                print(f"Warning: Exception occurred during read_rolls: {e}. Reloading page...")
                self.open_page()
                continue

    def read_rolls(self):
        if not self.page:
            raise RuntimeError("Page not opened")

        self.page.wait_for_selector("div.previous-rolls-item > div", timeout=30000)
        elements = self.page.query_selector_all("div.previous-rolls-item > div")
        labels  = []
        for el in elements:
            cls = (el.get_attribute("class") or "").lower()
            if "coin-ct" in cls:
                labels.append("CT")
            elif "coin-t" in cls:
                labels.append("T")
            elif "coin-bonus" in cls:
                labels.append("BONUS")
            else:
                labels.append("UNKNOWN")
        return labels

def ensure_csv(csv_path="rolls.csv"):
    if not os.path.exists(csv_path):
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "roll"])

scraper = CSGOEmpireScraper()
scraper.track_roulette()
scraper.close()