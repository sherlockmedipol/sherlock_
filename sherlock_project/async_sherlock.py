"""
Sherlock Async Engine - Asenkron HTTP motoru
aiohttp ile requests-futures yerine gecis

Features:
    - aiohttp ClientSession ile baglanti havuzu
    - asyncio.Semaphore ile eszamanli istek limiti
    - WAF (Cloudflare, PerimeterX) tespiti
    - Exponential backoff ile retry mekanizmasi
    - Proxy destegi
    - Progress callback ile gercek zamanli ilerleme
"""

import asyncio
import aiohttp
import aiofiles
from aiohttp import ClientTimeout, TCPConnector
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from time import monotonic
import json
from pathlib import Path

from sherlock_project.result import QueryStatus, QueryResult
from sherlock_project.sites import SitesInformation
from sherlock_project.notify import QueryNotify


# Bilinen WAF imzalari
WAF_SIGNATURES = [
    'cf-browser-verification',          # Cloudflare
    'challenge-platform',               # Cloudflare Turnstile
    'AwsWafIntegration',                # AWS WAF (Cloudfront)
    'perimeterxIdentifiers',             # PerimeterX / Human Security
    'blocked?reason=',                   # Generic WAF
    'unusual traffic',                   # Google / Cloudflare
]

# User-Agent havuzu - her istekte rotate edilir
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0',
]


@dataclass
class ScanConfig:
    """Tarama konfigurasyonu"""
    max_concurrent: int = 20
    timeout: float = 10.0
    max_retries: int = 3
    retry_delay: float = 1.0
    respect_robots_txt: bool = False
    rotate_user_agent: bool = True
    waf_detection: bool = True

    def __post_init__(self):
        """Deger dogrulama"""
        assert self.max_concurrent > 0, "max_concurrent must be positive"
        assert self.timeout > 0, "timeout must be positive"
        assert self.max_retries >= 0, "max_retries must be non-negative"
        assert self.retry_delay > 0, "retry_delay must be positive"


class AsyncSherlock:
    """Asenkron Sherlock motoru"""

    def __init__(
        self,
        sites: SitesInformation,
        config: ScanConfig = None,
        notifier: Optional[QueryNotify] = None,
        proxy: Optional[str] = None
    ):
        self.sites = sites
        self.config = config or ScanConfig()
        self.notifier = notifier
        self.proxy = proxy
        self.results: List[QueryResult] = []
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._ua_index: int = 0

    def _get_user_agent(self) -> str:
        """User-Agent dondur (rotate ederek)"""
        if not self.config.rotate_user_agent:
            return USER_AGENTS[0]
        ua = USER_AGENTS[self._ua_index % len(USER_AGENTS)]
        self._ua_index += 1
        return ua

    async def __aenter__(self):
        """Async context manager giris"""
        connector = TCPConnector(
            limit=self.config.max_concurrent * 2,
            limit_per_host=5,
            enable_cleanup_closed=True,
            force_close=True,
            ttl_dns_cache=300,
        )
        timeout = ClientTimeout(
            total=self.config.timeout,
            connect=self.config.timeout * 0.3,
            sock_read=self.config.timeout * 0.7,
        )

        self._session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
        )
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager cikis"""
        if self._session:
            await self._session.close()

    def _detect_waf(self, text: str, headers: dict) -> bool:
        """WAF tarafindan engellenip engellenmedigini kontrol et"""
        if not self.config.waf_detection:
            return False

        for signature in WAF_SIGNATURES:
            if signature.lower() in text.lower():
                return True

        server = headers.get('Server', '').lower()
        if any(waf in server for waf in ['cloudflare', 'akamai', 'incapsula']):
            return True

        cf_ray = headers.get('CF-Ray', '')
        if cf_ray:
            return True

        return False

    async def _check_site(
        self,
        username: str,
        site_name: str,
        site_info
    ) -> QueryResult:
        """Tek site kontrolu"""
        url = site_info.url_username_format.format(username)
        url_main = site_info.url_home
        error_type = site_info.information.get('errorType', '')
        error_msg = site_info.information.get('errorMsg', [])

        start_time = monotonic()
        status = QueryStatus.UNKNOWN
        http_status = 0
        context = {}

        async with self._semaphore:
            for attempt in range(self.config.max_retries + 1):
                try:
                    headers = {}
                    if self.config.rotate_user_agent:
                        headers['User-Agent'] = self._get_user_agent()

                    async with self._session.get(
                        url,
                        proxy=self.proxy,
                        allow_redirects=True,
                        headers=headers,
                    ) as response:
                        http_status = response.status
                        text = await response.text()
                        response_time = monotonic() - start_time

                        if self._detect_waf(text, dict(response.headers)):
                            status = QueryStatus.WAF
                            context = {
                                'waf_detected': True,
                                'response_time': round(response_time, 3),
                                'http_status': http_status,
                                'final_url': str(response.url)
                            }
                            break

                        if error_type == 'message':
                            status = (
                                QueryStatus.CLAIMED
                                if all(m not in text for m in error_msg)
                                else QueryStatus.AVAILABLE
                            )
                        elif error_type == 'status_code':
                            if isinstance(error_msg, (list, tuple)):
                                status = (
                                    QueryStatus.AVAILABLE
                                    if response.status in error_msg
                                    else QueryStatus.CLAIMED
                                )
                            else:
                                status = (
                                    QueryStatus.AVAILABLE
                                    if response.status == error_msg
                                    else QueryStatus.CLAIMED
                                )
                        elif error_type == 'response_url':
                            final_url = str(response.url)
                            status = (
                                QueryStatus.AVAILABLE
                                if final_url != url
                                else QueryStatus.CLAIMED
                            )

                        context = {
                            'response_time': round(response_time, 3),
                            'http_status': http_status,
                            'final_url': str(response.url)
                        }
                        break

                except asyncio.TimeoutError:
                    if attempt < self.config.max_retries:
                        await asyncio.sleep(self.config.retry_delay * (2 ** attempt))
                    else:
                        status = QueryStatus.UNKNOWN
                        context = {'error': 'Timeout after retries'}

                except aiohttp.ClientConnectorError as e:
                    if attempt < self.config.max_retries:
                        await asyncio.sleep(self.config.retry_delay * (2 ** attempt))
                    else:
                        status = QueryStatus.UNKNOWN
                        context = {'error': f'Connection error: {str(e)}'}

                except aiohttp.ClientResponseError as e:
                    status = QueryStatus.UNKNOWN
                    context = {'error': f'HTTP error {e.status}: {str(e)}'}
                    break

                except Exception as e:
                    if attempt < self.config.max_retries:
                        await asyncio.sleep(self.config.retry_delay * (2 ** attempt))
                    else:
                        status = QueryStatus.UNKNOWN
                        context = {'error': str(e)}

        result = QueryResult(
            username=username,
            site_name=site_info.name,
            site_url_user=url,
            status=status,
            query_time=context.get('response_time', 0),
            context=context
        )

        if self.notifier:
            self.notifier.update(result)

        return result

    async def scan(
        self,
        username: str,
        site_list: Optional[List[str]] = None,
        progress_callback: Optional[Callable] = None,
        timeout: Optional[float] = None,
    ) -> List[QueryResult]:
        """
        Kullanici adi taramasi yap

        Args:
            username: Aranacak kullanici adi
            site_list: Belirli siteler (None = tumu)
            progress_callback: Ilerleme guncelleme callback'i
            timeout: Zaman asimi (varsayilan config'deki)

        Returns:
            Tarama sonuclari listesi
        """
        self.results = []

        if timeout is not None:
            old_timeout = self.config.timeout
            self.config.timeout = timeout
        else:
            old_timeout = None

        try:
            if site_list:
                sites_to_check = {
                    name: data for name, data in self.sites.sites.items()
                    if name in site_list
                }
            else:
                sites_to_check = dict(self.sites.sites.items())

            total = len(sites_to_check)
            completed = 0

            tasks = [
                self._check_site(username, site_name, site_info)
                for site_name, site_info in sites_to_check.items()
            ]

            for coro in asyncio.as_completed(tasks):
                result = await coro
                self.results.append(result)
                completed += 1

                if progress_callback:
                    progress_callback(completed, total, result)

        finally:
            if old_timeout is not None:
                self.config.timeout = old_timeout

        return self.results

    async def scan_multiple(
        self,
        usernames: List[str],
        site_list: Optional[List[str]] = None,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, List[QueryResult]]:
        """
        Birden fazla kullanici adi taramasi
        """
        results = {}
        for username in usernames:
            results[username] = await self.scan(
                username, site_list, progress_callback
            )
        return results


async def run_scan(
    username: str,
    sites: SitesInformation,
    config: Optional[ScanConfig] = None,
    notifier: Optional[QueryNotify] = None,
    proxy: Optional[str] = None,
    site_list: Optional[List[str]] = None
) -> List[QueryResult]:
    """
    Kolay kullanim icin async scan fonksiyonu
    """
    config = config or ScanConfig()

    async with AsyncSherlock(sites, config, notifier, proxy) as scanner:
        return await scanner.scan(username, site_list)