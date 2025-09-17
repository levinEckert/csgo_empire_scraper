from playwright.sync_api import sync_playwright
import time
import csv
from datetime import datetime

class CSGOEmpireScraper:
    def __init__(self):
        self.url = "https://csgoempire.com/"

    def open_page(self):
        try:
            with sync_playwright() as p:
                # Keep the Playwright context open while the page is visible
                browser = p.chromium.launch(headless=False)
                page = browser.new_page()
                page.goto(self.url)
                title = page.title()
                print(f"[INFO] Page title: {title}")

                # Wait without blocking to keep the window open
                time.sleep(10)

                # Properly close the browser
                browser.close()
        except Exception as e:
            print("[ERROR] Failed to launch/navigate with Playwright. If this is a fresh install, run 'python -m playwright install' (or 'playwright install') in your virtualenv.")
            print(f"[ERROR] Exception: {e}")

    def track_latest_change(self, poll_interval=1.0, runtime=300):
        """
        Continuously logs the newest change in the last roll on the page.
        """
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                page = browser.new_page()
                page.goto(self.url)
                print("[INFO] Started tracking latest roll changes...")

                last_seen = None
                start_time = time.time()

                while (time.time() - start_time) < runtime:
                    try:
                        # Query all elements matching the selector
                        elements = page.query_selector_all("div.previous-rolls-item > div")
                        if not elements:
                            # No elements found, skip this iteration
                            time.sleep(poll_interval)
                            continue

                        last_element = elements[-1]
                        class_list = last_element.get_attribute("class") or ""
                        # Determine roll type based on class
                        if "coin-ct" in class_list:
                            roll = "CT"
                        elif "coin-t" in class_list:
                            roll = "T"
                        elif "coin-bonus" in class_list:
                            roll = "BONUS"
                        else:
                            roll = "UNKNOWN"

                        if roll != last_seen:
                            print(f"[NEW ROLL] {roll}")
                            last_seen = roll

                    except Exception as inner_e:
                        print(f"[WARNING] Error while fetching roll data: {inner_e}")
                        # Skip this iteration on error

                    time.sleep(poll_interval)

                browser.close()
                print("[INFO] Finished tracking latest roll changes.")

        except Exception as e:
            print("[ERROR] Failed to launch/navigate with Playwright for tracking latest changes.")
            print(f"[ERROR] Exception: {e}")

    def track_to_csv(self, csv_path="rolls.csv"):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                page = browser.new_page()
                page.goto(self.url)
                print(f"[INFO] Started event-based tracking. Writing to {csv_path}")

                # Ensure CSV has a header if the file is empty/non-existent
                try:
                    with open(csv_path, "x", newline="") as f:
                        writer = csv.writer(f)
                        writer.writerow(["timestamp", "roll"])  # header
                except FileExistsError:
                    pass

                # Helper to append to CSV
                def append_roll(roll_value: str):
                    ts = datetime.utcnow().isoformat()
                    with open(csv_path, "a", newline="") as f:
                        writer = csv.writer(f)
                        writer.writerow([ts, roll_value])
                    print(f"[NEW ROLL] {roll_value} @ {ts}")

                # Expose a Python binding callable from the page context
                def report_roll_binding(source, roll_value):
                    # roll_value expected to be a simple string
                    append_roll(roll_value)

                page.expose_binding("reportRoll", report_roll_binding)

                # Install a MutationObserver that calls window.reportRoll when the last roll changes
                page.evaluate(
                    """
                    () => {
                        // Utility to map class -> label
                        const mapRoll = (el) => {
                            if (!el) return "UNKNOWN";
                            const cls = el.getAttribute("class") || "";
                            if (cls.includes("coin-ct")) return "CT";
                            if (cls.includes("coin-t")) return "T";
                            if (cls.includes("coin-bonus")) return "BONUS";
                            return "UNKNOWN";
                        };

                        const queryCoins = () => Array.from(document.querySelectorAll("div.previous-rolls-item > div"));
                        const newestCoinEl = () => {
                            const coins = queryCoins();
                            return coins.length ? coins[coins.length - 1] : null; // assumes newest is rightmost
                        };

                        // Track the actual DOM element reference and its class
                        let lastEl = newestCoinEl();
                        let lastLabel = mapRoll(lastEl);
                        if (lastEl) {
                            // Emit initial state once
                            window.reportRoll(lastLabel);
                        }

                        const target = document.querySelector(".relative.flex.h-24") || document.body;
                        let debounceId = null;
                        const observer = new MutationObserver((mutations) => {
                            // Debounce rapid DOM churn (animations, class flips, wrappers)
                            if (debounceId) clearTimeout(debounceId);
                            debounceId = setTimeout(() => {
                                const currentEl = newestCoinEl();
                                const currentLabel = mapRoll(currentEl);

                                // Only emit on real changes and ignore UNKNOWN noise
                                const changedEl = currentEl && currentEl !== lastEl;
                                const changedLabel = currentLabel !== lastLabel;
                                const isKnown = currentLabel === 'CT' || currentLabel === 'T' || currentLabel === 'BONUS';

                                if ((changedEl || changedLabel) && isKnown) {
                                    lastEl = currentEl;
                                    lastLabel = currentLabel;
                                    window.reportRoll(currentLabel);
                                }
                            }, 300); // 300ms debounce window; adjust if needed
                        });

                        observer.observe(target, { childList: true, subtree: true, attributes: true, attributeFilter: ['class'] });
                    }
                    """
                )

                print("[INFO] Observer installed. Press Ctrl+C to stop.")

                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    print("\n[INFO] Stopping tracking...")
                finally:
                    browser.close()
                    print("[INFO] Browser closed.")
        except Exception as e:
            print("[ERROR] Failed to set up event-based tracking with Playwright.")
            print(f"[ERROR] Exception: {e}")

    def track_polling_csv(self, csv_path="rolls.csv", interval_sec=5, max_minutes=None):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
                page = browser.new_page()
                page.goto(self.url, wait_until="domcontentloaded")
                try:
                    page.wait_for_selector("div.previous-rolls-item > div", timeout=30000)
                except Exception:
                    print("[WARNING] Rolls container not found within 30s; continuing anyway.")
                print(f"[INFO] Started polling-based tracking. Writing to {csv_path}")

                # Ensure CSV has a header if the file is empty/non-existent
                try:
                    with open(csv_path, "x", newline="") as f:
                        writer = csv.writer(f)
                        writer.writerow(["timestamp", "roll"])  # header
                except FileExistsError:
                    pass

                def _read_rolls():
                    elements = page.query_selector_all("div.previous-rolls-item > div")
                    rolls = []
                    for el in elements:
                        cls = el.get_attribute("class") or ""
                        if "coin-ct" in cls:
                            rolls.append("CT")
                        elif "coin-t" in cls:
                            rolls.append("T")
                        elif "coin-bonus" in cls:
                            rolls.append("BONUS")
                        else:
                            rolls.append("UNKNOWN")
                    return rolls

                prev = None
                start_time = time.time()
                last_activity = time.time()
                reload_interval = 300  # seconds (5 minutes)

                while True:
                    try:
                        curr = _read_rolls()
                        if prev is not None and len(curr) == len(prev):
                            n = len(curr)
                            logged = False
                            # Find m in 1..n such that prev[m:] == curr[:-m]
                            for m in range(1, n + 1):
                                if prev[m:] == curr[:-m]:
                                    new_items = curr[-m:]
                                    for item in new_items:
                                        if item in {"CT", "T", "BONUS"}:  # ignore UNKNOWN noise
                                            ts = datetime.utcnow().isoformat()
                                            with open(csv_path, "a", newline="") as f:
                                                writer = csv.writer(f)
                                                writer.writerow([ts, item])
                                            print(f"[NEW ROLL] {item} @ {ts}")
                                            last_activity = time.time()
                                    logged = True
                                    break
                            if not logged:
                                # No clean alignment found; reset baseline to current without logging
                                print("[DEBUG] No alignment with previous window; resetting baseline.")
                        prev = curr

                        if max_minutes is not None:
                            elapsed_minutes = (time.time() - start_time) / 60
                            if elapsed_minutes >= max_minutes:
                                print("[INFO] Maximum runtime reached, stopping polling.")
                                break

                        # Reload page if no new activity for too long
                        if (time.time() - last_activity) > reload_interval:
                            print("[INFO] No new rolls detected for a while; reloading page...")
                            try:
                                page.reload(wait_until="domcontentloaded")
                                page.wait_for_selector("div.previous-rolls-item > div", timeout=30000)
                                last_activity = time.time()
                                prev = None  # reset baseline after reload
                            except Exception as reload_e:
                                print(f"[WARNING] Reload failed: {reload_e}")

                        time.sleep(interval_sec)
                    except Exception as e:
                        print(f"[WARNING] Error during polling: {e}")
                        time.sleep(interval_sec)

                browser.close()
                print("[INFO] Finished polling-based tracking.")
        except Exception as e:
            print("[ERROR] Failed to set up polling-based tracking with Playwright.")
            print(f"[ERROR] Exception: {e}")

scraper = CSGOEmpireScraper()
scraper.track_polling_csv("rolls.csv", interval_sec=10)
