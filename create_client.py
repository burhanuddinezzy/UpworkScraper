import asyncio
import random
import json
import time
from os import getenv
from typing import Optional, Dict, Any, Union
from dataclasses import dataclass
from rnet import Impersonate, Client, Proxy, Response
from selectolax.parser import HTMLParser
from fake_useragent import UserAgent
from playwright.async_api import async_playwright, Browser as PWBrowser
from asynciolimiter import Limiter
from rich import print

@dataclass
class ClientConfig:
    use_proxy: bool = False
    proxy_url: Optional[str] = None
    rate_limit_rpm: int = 20
    enable_ua_rotation: bool = True
    enable_delay_jitter: bool = True
    min_delay: float = 1.0
    max_delay: float = 3.0
    max_retries: int = 1
    timeout: int = 30
    enable_tls_fingerprinting: bool = True
    enable_http2: bool = True

class SuperClient:
    def __init__(self):
        self.config = ClientConfig()
        self._last_request_time = 0
        self._request_count = 0
        self._playwright = None
        self._browser = None
        self._browser_context = None
        self.ua = UserAgent()
        self.current_ua = self.ua.random
        # Simple timestamp-based rate limiting (requests per minute)
        if self.config.rate_limit_rpm and self.config.rate_limit_rpm > 0:
            self._min_interval = 60.0 / float(self.config.rate_limit_rpm)
        else:
            self._min_interval = 0.0
        self.limiter = None
    
    def _get_proxies(self):
        proxy_url = self.config.proxy_url or getenv("PROXY")
        if not self.config.use_proxy or not proxy_url:
            return None
        return [Proxy.http(proxy_url), Proxy.https(proxy_url)]
    
    def _create_http_client(self):
        proxies = self._get_proxies()
        impersonate = Impersonate.Chrome120 if self.config.enable_tls_fingerprinting else None # or firefox136
        headers = {
            'User-Agent': self.current_ua,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'no-cache',
            'DNT': '1',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
        }
        return Client(impersonate=impersonate, proxies=proxies, headers=headers, timeout=self.config.timeout, http2=self.config.enable_http2)
    
    async def ensure_browser(self, headless=True):
        if self._browser is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-features=IsolateOrigins,site-per-process',
                ]
            )
            self._browser_context = await self._browser.new_context(
                user_agent=self.current_ua,
                viewport={'width': 1920, 'height': 1080},
                java_script_enabled=True,
                bypass_csp=True,
            )
            print(f"✅ Browser initialized")

    def _calculate_delay(self):
        if not self.config.enable_delay_jitter:
            return 0
        return random.uniform(self.config.min_delay, self.config.max_delay)

    async def _handle_retry(self, attempt, url, error):
        if attempt >= self.config.max_retries:
            raise error or Exception(f"Max retries exceeded for {url}")
        backoff_time = (2 ** attempt) + random.uniform(0, 1)
        await asyncio.sleep(backoff_time)
    
    async def get(self, url, **kwargs):
        return await self._get_with_http(url, **kwargs)

    async def get_with_browser(self, url, wait_until="networkidle", timeout=30000, **kwargs):
        if self._browser is None:
            raise RuntimeError("Browser not initialized. Call ensure_browser() first.")
        
        for attempt in range(self.config.max_retries + 1):
            try:
                await self._apply_delay()
                page = await self._browser_context.new_page()
                
                # Add common browser automation protections
                await page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    window.chrome = { runtime: {} };
                """)
                
                response = await page.goto(
                    url, 
                    wait_until=wait_until, 
                    timeout=timeout
                )
                
                if not response:
                    raise Exception("No response from browser")
                
                content = await page.content()
                
                if self._check_blocking_indicators(content, response.status):
                    if attempt < self.config.max_retries:
                        print(f"[yellow]🚨 Browser blocked, retrying...[/yellow]")
                        await page.close()
                        await self._handle_retry(attempt, url)
                        continue
                    else:
                        raise Exception("Browser still blocked after retries")
                
                await page.close()
                return content
                
            except Exception as e:
                if attempt < self.config.max_retries:
                    await self._handle_retry(attempt, url, e)
                else:
                    print(f"[red]❌ Browser failed after {self.config.max_retries} retries: {e}[/red]")
                    raise

    async def _get_with_http(self, url, **kwargs):
        client = self._create_http_client()
        for attempt in range(self.config.max_retries + 1):
            try:
                # Enforce per-minute rate limit using a minimal interval between requests
                if getattr(self, "_min_interval", 0) > 0:
                    now = time.monotonic()
                    elapsed = now - (self._last_request_time or 0)
                    if elapsed < self._min_interval:
                        await asyncio.sleep(self._min_interval - elapsed)

                await self._apply_delay()
                response = await client.get(url, **kwargs)
                self._last_request_time = time.monotonic()
                if self._is_blocked(response):
                    if attempt < self.config.max_retries:
                        print(f"[yellow]🚨 Blocking detected, retrying...[/yellow]")
                        await self._handle_retry(attempt, url)
                        continue
                    else:
                        raise Exception(f"Still blocked after {self.config.max_retries} retries")
                if self.config.enable_ua_rotation:
                    self.current_ua = self.ua.random
                self._request_count += 1
                return response
            except Exception as e:
                if attempt < self.config.max_retries:
                    await self._handle_retry(attempt, url, e)
                else:
                    print(f"[red]❌ Failed after {self.config.max_retries} retries: {e}[/red]")
                    raise
    
    async def _apply_delay(self):
        delay = self._calculate_delay()
        if delay > 0:
            await asyncio.sleep(delay)
    
    def _is_blocked(self, response):
        return response.status_code in [403, 429, 503, 509]
    
    def _check_blocking_indicators(self, text, status_code):
        if status_code in [403, 429, 503, 509]:
            return True
        text_lower = text.lower()
        blocking_indicators = ["captcha", "challenge", "robot", "automated", "bot", "access denied", "blocked", "security check", "cloudflare", "distil", "datadome", "incapsula", "akamai", "perimeterx", "sorry we just need to make sure", "unusual traffic"]
        return any(indicator in text_lower for indicator in blocking_indicators)
    
    async def close(self):
        if self._browser:
            await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
            self._browser = None
            self._browser_context = None
            self._playwright = None

async def amazon_scraping_example():
    config = ClientConfig(
        use_proxy=False,
        proxy_url="",
        rate_limit_rpm=60,
        min_delay=1.0,  # Adjust these values as needed
        max_delay=3.0   # Adjust these values as needed
    )
    client = SuperClient()
    
    try:
        try: # Option 1: Try with HTTP client first (faster)
            response = await client.get("https://www.amazon.com/dp/B08N5WRWNW")
            if client._is_blocked(response):
                raise Exception("Blocked")
            print(response.status_code)
        except: # Option 2: Use browser if HTTP fails
            await client.ensure_browser()
            html_content = await client.get_with_browser("https://www.amazon.com/dp/B08N5WRWNW")
            print(html_content.status_code)
    finally:
        await client.close()



async def upwork():
    client = SuperClient()
    
    try:
        response = await client.get("https://www.upwork.com/nx/find-work/best-matches")
        if client._is_blocked(response):
            raise Exception("Blocked")
        print(response.status_code)
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(upwork())