import os, re, time, json
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

EPAPER_URL = "https://www.limmatwelle.ch/e-paper"
TARGET_TEXTS = ["Woche 21", "22. Mai"]       # what to match on the card
OUTPUT_PATH  = r"C:\RPA Python Reader\input\limmatwelle-22-mai.pdf"


def _prepare_chrome(download_dir: str) -> webdriver.Chrome:
    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
        "plugins.always_open_pdf_externally": True,  # download PDFs instead of previewing
    }
    opts = Options()
    # Run NON-headless to look like a real user (headless often gets blocked by Issuu)
    # opts.add_argument("--headless=new")
    opts.add_experimental_option("prefs", prefs)
    opts.add_argument("--window-size=1400,960")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    # Enable performance logging to read network requests
    caps = {
        "goog:loggingPrefs": {"performance": "ALL"},
        "browserName": "chrome",
    }
    driver = webdriver.Chrome(options=opts, desired_capabilities=caps)
    return driver


def _dismiss_cookie_banners(driver: webdriver.Chrome):
    for xp in [
        "//button[contains(., 'Akzeptieren') or contains(., 'Einverstanden') or contains(., 'Accept')]",
        "//button[contains(., 'OK')]",
        "//button[contains(., 'Zustimmen')]",
    ]:
        try:
            btn = driver.find_element(By.XPATH, xp)
            btn.click()
            time.sleep(1)
            break
        except Exception:
            pass


def _find_issue_href_by_text(driver: webdriver.Chrome) -> str:
    """Scroll the page to find an <a> whose visible text contains all TARGET_TEXTS."""
    last_top = -1
    for _ in range(40):  # up to ~40 scrolls
        anchors = driver.find_elements(By.XPATH, "//a[normalize-space()]")
        for a in anchors:
            txt = a.text.strip().replace("\n", " ")
            if all(t.lower() in txt.lower() for t in TARGET_TEXTS):
                href = a.get_attribute("href")
                if href:
                    return href
        # Scroll down to load more cards
        driver.execute_script("window.scrollBy(0, document.documentElement.clientHeight * 0.9);")
        time.sleep(0.8)
        cur_top = driver.execute_script("return document.documentElement.scrollTop")
        if cur_top == last_top:  # reached bottom
            break
        last_top = cur_top
    raise RuntimeError("Could not find the 'Woche 21 / 22. Mai' card by text.")


def _get_pdf_url_from_perf_logs(driver: webdriver.Chrome, timeout: int = 20) -> str:
    """
    Read Chrome performance logs for requests to a .pdf; return the first matching URL.
    Works on Issuu because the viewer fetches the real PDF via XHR/fetch.
    """
    start = time.time()
    seen = set()
    while time.time() - start < timeout:
        for entry in driver.get_log("performance"):
            try:
                msg = json.loads(entry["message"])["message"]
            except Exception:
                continue
            method = msg.get("method", "")
            if method not in ("Network.requestWillBeSent", "Network.responseReceived"):
                continue
            params = msg.get("params", {})
            url = params.get("request", {}).get("url") or params.get("response", {}).get("url")
            if not url or url in seen:
                continue
            seen.add(url)
            if url.lower().endswith(".pdf"):
                return url
        time.sleep(0.3)
    return ""


def _wait_for_download(target_path: str, dl_dir: str, timeout: int = 120) -> str:
    target_path = os.path.abspath(target_path)
    start = time.time()
    while time.time() - start < timeout:
        if os.path.exists(target_path) and os.path.getsize(target_path) > 1024:
            return target_path
        # rename newest PDF if Issuu used a random filename
        newest_pdf = None
        for p in Path(dl_dir).glob("*.pdf"):
            if newest_pdf is None or p.stat().st_mtime > newest_pdf.stat().st_mtime:
                newest_pdf = p
        if newest_pdf and time.time() - newest_pdf.stat().st_mtime < 90 and newest_pdf.stat().st_size > 1024:
            os.replace(str(newest_pdf), target_path)
            return target_path
        time.sleep(0.8)
    raise RuntimeError("Timed out waiting for the PDF to download.")


def download_issue_pdf(out_path: str) -> str:
    import os, re, time, json
    from pathlib import Path
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.keys import Keys

    EPAPER_URL = "https://www.limmatwelle.ch/e-paper"
    TARGET_TEXTS = ["Woche 21", "22. Mai"]

    def _prepare_chrome(download_dir: str) -> webdriver.Chrome:
        prefs = {
            "download.default_directory": download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
            "plugins.always_open_pdf_externally": True,
        }
        opts = Options()
        # Run non-headless to look like a real user (headless gets blocked often)
        # opts.add_argument("--headless=new")
        opts.add_experimental_option("prefs", prefs)
        opts.add_argument("--window-size=1400,960")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")

        caps = {"goog:loggingPrefs": {"performance": "ALL"}}
        driver = webdriver.Chrome(options=opts, desired_capabilities=caps)

        # Enable CDP Network to get mimeTypes in logs
        try:
            driver.execute_cdp_cmd("Network.enable", {})
            driver.execute_cdp_cmd("Page.enable", {})
        except Exception:
            pass
        return driver

    def _dismiss_cookie_banners(driver: webdriver.Chrome):
        for xp in [
            "//button[contains(., 'Akzeptieren') or contains(., 'Einverstanden') or contains(., 'Accept')]",
            "//button[contains(., 'OK')]",
            "//button[contains(., 'Zustimmen')]",
        ]:
            try:
                driver.find_element(By.XPATH, xp).click()
                time.sleep(0.8)
                break
            except Exception:
                pass

    def _find_issue_href_by_text(driver: webdriver.Chrome) -> str:
        last_top = -1
        for _ in range(40):
            anchors = driver.find_elements(By.XPATH, "//a[normalize-space()]")
            for a in anchors:
                txt = a.text.strip().replace("\n", " ")
                if all(t.lower() in txt.lower() for t in TARGET_TEXTS):
                    href = a.get_attribute("href")
                    if href:
                        return href
            driver.execute_script("window.scrollBy(0, document.documentElement.clientHeight * 0.9);")
            time.sleep(0.8)
            cur_top = driver.execute_script("return document.documentElement.scrollTop")
            if cur_top == last_top:
                break
            last_top = cur_top
        raise RuntimeError("Could not find the 'Woche 21 / 22. Mai' card by text.")

    def _get_pdf_from_perf_logs(driver: webdriver.Chrome, timeout: int = 30) -> str:
        start = time.time()
        seen = set()
        while time.time() - start < timeout:
            for entry in driver.get_log("performance"):
                try:
                    msg = json.loads(entry["message"])["message"]
                except Exception:
                    continue
                if msg.get("method") != "Network.responseReceived":
                    continue
                params = msg.get("params", {})
                resp = params.get("response", {}) or {}
                url = resp.get("url", "")
                mtype = resp.get("mimeType", "")
                if not url or url in seen:
                    continue
                seen.add(url)
                # Accept either explicit PDF MIME or .pdf suffix
                if mtype.lower() == "application/pdf" or url.lower().endswith(".pdf"):
                    return url
            time.sleep(0.3)
        return ""

    def _click_viewer_download(driver: webdriver.Chrome):
        """
        Try multiple selectors that Issuu uses for its Download control.
        If found, click; otherwise no-op.
        """
        xpaths = [
            # Button with visible text
            "//button[contains(., 'Download') or contains(., 'Herunterladen')]",
            # aria-label
            "//*[@aria-label='Download' or @aria-label='Herunterladen']",
            # title/tooltips
            "//*[@title='Download' or @title='Herunterladen']",
            # data-testid/data-qa
            "//*[@data-testid='download' or @data-qa='download']",
            # svg icon inside a button
            "//button[.//*[name()='svg' and (@aria-label='Download' or @title='Download')]]",
        ]
        for xp in xpaths:
            try:
                btn = driver.find_element(By.XPATH, xp)
                btn.click()
                return True
            except Exception:
                pass
        # As a last resort, send Ctrl+S (sometimes triggers browser save dialog—not ideal, but try)
        try:
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.CONTROL, 's')
        except Exception:
            pass
        return False

    def _wait_for_download(target_path: str, dl_dir: str, timeout: int = 120) -> str:
        target_path = os.path.abspath(target_path)
        start = time.time()
        while time.time() - start < timeout:
            if os.path.exists(target_path) and os.path.getsize(target_path) > 1024:
                return target_path
            newest_pdf = None
            for p in Path(dl_dir).glob("*.pdf"):
                if newest_pdf is None or p.stat().st_mtime > newest_pdf.stat().st_mtime:
                    newest_pdf = p
            if newest_pdf and time.time() - newest_pdf.stat().st_mtime < 90 and newest_pdf.stat().st_size > 1024:
                os.replace(str(newest_pdf), target_path)
                return target_path
            time.sleep(0.8)
        raise RuntimeError("Timed out waiting for the PDF to download.")

    out_path = os.path.abspath(out_path)
    dl_dir = os.path.dirname(out_path)
    os.makedirs(dl_dir, exist_ok=True)
    for p in (out_path, out_path + ".crdownload"):
        if os.path.exists(p):
            try: os.remove(p)
            except: pass

    driver = _prepare_chrome(dl_dir)
    try:
        # 1) Open list page and find the issue
        driver.get(EPAPER_URL)
        time.sleep(2)
        _dismiss_cookie_banners(driver)
        href = _find_issue_href_by_text(driver)

        # 2) Navigate to Issuu viewer (switch to new tab if needed)
        driver.get(href)
        time.sleep(5)
        if len(driver.window_handles) > 1:
            driver.switch_to.window(driver.window_handles[-1])

        # ---- Accept Cookiebot banner if visible ----
        try:
            cookie_button = driver.find_element(
                By.XPATH,
                "//button[contains(., 'Allow all cookies') or contains(., 'Alle Cookies erlauben')]"
            )
            driver.execute_script("arguments[0].scrollIntoView(true);", cookie_button)
            time.sleep(1)
            cookie_button.click()
            print("[INFO] Accepted Cookiebot consent banner.")
            time.sleep(2)
        except Exception as e:
            print("[WARN] Cookiebot banner not found or already accepted:", e)

        # 3) Wait for Issuu viewer to load fully
        time.sleep(6)

        # 4) Try clicking the Download button directly
        clicked = False
        for xp in [
            "//button[contains(., 'Download') or contains(., 'Herunterladen')]",
            "//*[@aria-label='Download' or @title='Download']",
            "//*[contains(@data-testid, 'download') or contains(@data-qa, 'download')]",
            "//a[contains(@href, '.pdf')]",
        ]:
            try:
                btn = driver.find_element(By.XPATH, xp)
                driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                time.sleep(1)
                btn.click()
                print(f"[INFO] Clicked Issuu download button: {xp}")
                clicked = True
                break
            except Exception:
                pass

        if not clicked:
            print("[WARN] No visible download button found; trying Ctrl+S fallback...")
            try:
                from selenium.webdriver.common.keys import Keys
                driver.find_element(By.TAG_NAME, "body").send_keys(Keys.CONTROL, 's')
            except Exception:
                pass

        # 5) Wait for the PDF to appear in the download directory
        downloaded_path = _wait_for_download(out_path, dl_dir, timeout=180)
        print(f"[INFO] Download completed: {downloaded_path}")
        return downloaded_path

    finally:
        driver.quit()

if __name__ == "__main__":
    saved = download_issue_pdf(OUTPUT_PATH)
    print("Saved to:", saved)
