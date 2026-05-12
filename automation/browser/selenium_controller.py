"""
automation/browser/selenium_controller.py
------------------------------------------
Selenium fallback browser controller.
Used when Playwright fails or as an alternative browser driver.
"""

import logging
from typing import Optional
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)


class SeleniumController:
    """Selenium-based browser controller (fallback for Playwright)."""

    def __init__(self):
        self._driver = None
        self._available = False
        self._initialize()

    def _initialize(self) -> None:
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            from webdriver_manager.chrome import ChromeDriverManager

            options = Options()
            options.add_argument("--start-maximized")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)

            service = Service(ChromeDriverManager().install())
            self._driver = webdriver.Chrome(service=service, options=options)
            self._available = True
            logger.info("Selenium Chrome driver initialized")
        except Exception as e:
            logger.warning(f"Selenium unavailable: {e}")
            self._available = False

    def open_url(self, url: str) -> bool:
        if not self._available or not self._driver:
            return False
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            self._driver.get(url)
            logger.info(f"Selenium opened: {url}")
            return True
        except Exception as e:
            logger.error(f"Selenium open_url error: {e}")
            return False

    def search_google(self, query: str) -> bool:
        return self.open_url(f"https://www.google.com/search?q={quote_plus(query)}")

    def search_youtube(self, query: str) -> bool:
        return self.open_url(f"https://www.youtube.com/results?search_query={quote_plus(query)}")

    def close(self) -> None:
        if self._driver:
            try:
                self._driver.quit()
            except Exception:
                pass
            self._driver = None
            self._available = False

    @property
    def is_available(self) -> bool:
        return self._available

    def __repr__(self) -> str:
        return f"SeleniumController(available={self._available})"
