import os
import time
import json
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from robot.api.deco import keyword  # ✅ Expose to Robot Framework

# ---------------- Config ----------------
EPAPER_URL = "https://www.limmatwelle.ch/e-paper"
TARGET_TEXTS = ["Woche 21", "22. Mai"]
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# ---------------- Browser Setup ----------------
def _prepare_chrome(download_dir: str, headless: bool = False) -> webdriver.Chrome:
    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "plugins.always_open_pdf_externally": True,
        "safebrowsing.enabled": True,
    }
    opts = Options()
    opts.add_experimental_option("prefs", prefs)
    opts.add_argument(f"--user-agent={DEFAULT_USER_AGENT}")
    opts.add_argument("--window-size=1400,960")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    if headless:
        opts.add_argument("--headless=new")

    caps = {"goog:loggingPrefs": {"performance": "ALL"}}
    driver = webdriver.Chrome(options=opts, desired_capabilities=caps)
    try:
        driver.execute_cdp_cmd("Network.enable", {})
    except Exception:
        pass
    return driver


# ---------------- Helpers ----------------
def _wait_click(driver, xpath: str, timeout: int = 10) -> bool:
    try:
        el = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.XPATH, xpath)))
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        el.click()
        return True
    except Exception:
        return False


def _dismiss_cookies(driver):
    for xp in [
        "//button[contains(., 'Allow all cookies') or contains(., 'Alle Cookies erlauben')]",
        "//button[contains(., 'Akzeptieren') or contains(., 'Einverstanden') or contains(., 'Accept')]",
        "//button[contains(., 'OK')]",
        "//button[contains(., 'Zustimmen')]",
    ]:
        if _wait_click(driver, xp, timeout=5):
            print(f"[INFO] Cookie banner dismissed: {xp}")
            return


def _find_issue_href(driver) -> str:
    """Scroll until the correct issue link is found."""
    for _ in range(30):
        anchors = driver.find_elements(By.XPATH, "//a[normalize-space()]")
        for a in anchors:
            txt = a.text.strip().replace("\n", " ")
            if all(t.lower() in txt.lower() for t in TARGET_TEXTS):
                href = a.get_attribute("href")
                if href:
                    return href
        driver.execute_script("window.scrollBy(0, document.documentElement.clientHeight * 0.9);")
        time.sleep(0.5)
    raise RuntimeError(f"Could not find issue with texts {TARGET_TEXTS}")


def _wait_for_download(target_path: str, dl_dir: str, timeout: int = 120) -> str:
    """Wait for a .pdf file to appear and move it to target_path."""
    final = os.path.abspath(target_path)
    start = time.time()
    while time.time() - start < timeout:
        # direct file ready
        if os.path.exists(final) and os.path.getsize(final) > 1024:
            return final
        # check for any pdf in folder
        pdfs = sorted(Path(dl_dir).glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
        if pdfs and pdfs[0].stat().st_size > 1024:
            os.replace(pdfs[0], final)
            return final
        time.sleep(0.5)
    raise TimeoutError("Download did not complete in time.")


# ---------------- Main Keyword ----------------
@keyword("Download Issue Pdf")
def download_issue_pdf(out_path: str) -> str:
    """
    Robot Keyword: Download the latest Baugesuch issue PDF.
    Example:
        ${pdf}=    Download Issue Pdf    ${CURDIR}${/}input${/}limmatwelle-22-mai.pdf
    """
    out_path = os.path.abspath(out_path)
    dl_dir = os.path.dirname(out_path)
    os.makedirs(dl_dir, exist_ok=True)
    for p in (out_path, out_path + ".crdownload"):
        if os.path.exists(p):
            os.remove(p)

    driver = _prepare_chrome(dl_dir)
    try:
        driver.get(EPAPER_URL)
        _dismiss_cookies(driver)
        href = _find_issue_href(driver)

        driver.get(href)
        _dismiss_cookies(driver)
        time.sleep(3)

        # Click possible download buttons
        xpaths = [
            "//button[contains(., 'Download') or contains(., 'Herunterladen')]",
            "//*[@aria-label='Download' or @title='Download']",
            "//*[contains(@data-testid, 'download')]",
            "//a[contains(@href, '.pdf')]",
        ]
        for xp in xpaths:
            if _wait_click(driver, xp, timeout=6):
                print(f"[INFO] Clicked button: {xp}")
                break

        pdf_path = _wait_for_download(out_path, dl_dir, timeout=180)
        print(f"[INFO] Download successful: {pdf_path}")
        return pdf_path

    finally:
        driver.quit()


if __name__ == "__main__":
    OUTPUT_PATH = r"C:\RPA Python Reader\input\limmatwelle-22-mai.pdf"
    print("Saved to:", download_issue_pdf(OUTPUT_PATH))
