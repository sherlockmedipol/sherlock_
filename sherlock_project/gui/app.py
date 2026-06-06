"""
Sherlock Desktop - Ana GUI Uygulamasi
customtkinter tabanli masaustu arayuzu
"""

import customtkinter as ctk
import asyncio
import threading
from pathlib import Path
from typing import Optional, Coroutine, Any, Callable, List
from concurrent.futures import ThreadPoolExecutor

from sherlock_project.__init__ import __version__, __longname__
from sherlock_project.sites import SitesInformation
from sherlock_project.storage import LocalStorage
from sherlock_project.async_sherlock import AsyncSherlock, ScanConfig


class SherlockApp(ctk.CTk):
    """Sherlock Masaustu Ana Pencere"""

    def __init__(self):
        super().__init__()

        # Tema ayarlari
        ctk.set_appearance_mode('dark')
        ctk.set_default_color_theme('blue')

        # Pencere ayarlari
        self.title(f'{__longname__} v{__version__}')
        self.geometry('1200x800')
        self.minsize(900, 600)

        # Veri yonetimi
        self.sites = SitesInformation()
        self.storage = LocalStorage()
        self.current_results = []

        # UI Olustur
        self._create_layout()
        self._create_sidebar()
        self._create_main_content()

    def _create_layout(self):
        """Ana layout yapisi"""
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky='nsew')
        self.sidebar.grid_propagate(False)

        # Ana icerik
        self.main_frame = ctk.CTkFrame(self, corner_radius=0)
        self.main_frame.grid(row=0, column=1, sticky='nsew', padx=10, pady=10)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)

    def _create_sidebar(self):
        """Sol sidebar olustur"""
        # Logo/ Baslik
        self.logo_label = ctk.CTkLabel(
            self.sidebar,
            text='SHERLOCK',
            font=ctk.CTkFont(size=24, weight='bold')
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Versiyon
        self.version_label = ctk.CTkLabel(
            self.sidebar,
            text=f'v{__version__}',
            font=ctk.CTkFont(size=12),
            text_color='gray'
        )
        self.version_label.grid(row=1, column=0, padx=20, pady=(0, 20))

        # Menu butonlari
        self.menu_buttons = []
        menus = [
            ('Search', self._show_search),
            ('History', self._show_history),
            ('Statistics', self._show_stats),
            ('Site Manager', self._show_site_manager),
        ]

        for i, (text, command) in enumerate(menus, start=2):
            btn = ctk.CTkButton(
                self.sidebar,
                text=text,
                command=command,
                width=160,
                height=40,
                corner_radius=8
            )
            btn.grid(row=i, column=0, padx=20, pady=5)
            self.menu_buttons.append(btn)

        # Bosluk
        self.sidebar.grid_rowconfigure(6, weight=1)

        # Ayarlar
        self.settings_frame = ctk.CTkFrame(self.sidebar, fg_color='transparent')
        self.settings_frame.grid(row=7, column=0, padx=20, pady=10, sticky='ew')

        self.appearance_label = ctk.CTkLabel(
            self.settings_frame,
            text='Appearance:',
            font=ctk.CTkFont(size=12)
        )
        self.appearance_label.pack(anchor='w', pady=(0, 5))

        self.appearance_menu = ctk.CTkOptionMenu(
            self.settings_frame,
            values=['Dark', 'Light', 'System'],
            command=self._change_appearance
        )
        self.appearance_menu.pack(fill='x')

    def _create_main_content(self):
        """Ana icerik alani"""
        # Baslangic olarak arama ekrani goster
        from .search_frame import SearchFrame
        self.current_frame = SearchFrame(
            self.main_frame,
            sites=self.sites,
            storage=self.storage,
            on_results=self._on_search_results
        )
        self.current_frame.grid(row=0, column=0, sticky='nsew')

    def _show_search(self):
        """Arama ekranini goster"""
        self._clear_main_frame()
        from .search_frame import SearchFrame
        self.current_frame = SearchFrame(
            self.main_frame,
            sites=self.sites,
            storage=self.storage,
            on_results=self._on_search_results
        )
        self.current_frame.grid(row=0, column=0, sticky='nsew')

    def _show_history(self):
        """Gecmis ekranini goster"""
        self._clear_main_frame()
        from .history_frame import HistoryFrame
        self.current_frame = HistoryFrame(
            self.main_frame,
            storage=self.storage
        )
        self.current_frame.grid(row=0, column=0, sticky='nsew')

    def _show_stats(self):
        """Istatistik ekranini goster"""
        self._clear_main_frame()
        from .stats_frame import StatsFrame
        self.current_frame = StatsFrame(
            self.main_frame,
            storage=self.storage
        )
        self.current_frame.grid(row=0, column=0, sticky='nsew')

    def _show_site_manager(self):
        """Site yonetim ekranini goster"""
        self._clear_main_frame()
        from .site_manager import SiteManagerFrame
        self.current_frame = SiteManagerFrame(
            self.main_frame,
            sites=self.sites
        )
        self.current_frame.grid(row=0, column=0, sticky='nsew')

    def _clear_main_frame(self):
        """Mevcut frame'i temizle"""
        for widget in self.main_frame.winfo_children():
            widget.destroy()

    def _on_search_results(self, results):
        """Arama sonuclari callback"""
        self.current_results = results

    def _change_appearance(self, mode: str):
        """Tema degistir"""
        ctk.set_appearance_mode(mode.lower())

    def run_async(self, coro: Coroutine, callback: Optional[Callable] = None):
        """Async fonksiyon ayri thread'de calistir

        Args:
            coro: Calistirilacak coroutine
            callback: Sonucu almak icin callback (opsiyonel)
        """
        def _run():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(coro)
                loop.close()

                if callback:
                    self.after(0, lambda: callback(result))
            except Exception as e:
                if callback:
                    self.after(0, lambda: callback(None, e))

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

    def run_async_task(
        self,
        username: str,
        site_list: Optional[List[str]] = None,
        config: Optional[ScanConfig] = None,
        progress_callback: Optional[Callable] = None
    ):
        """Async taramayi baslat

        Ayri bir thread'de AsyncSherlock calistirir.
        """
        async def _scan():
            async with AsyncSherlock(
                self.sites,
                config or ScanConfig(),
                proxy=None
            ) as scanner:
                return await scanner.scan(
                    username,
                    site_list=site_list,
                    progress_callback=progress_callback
                )

        self.run_async(_scan())


def main():
    """Uygulama giris noktasi"""
    app = SherlockApp()
    app.mainloop()


if __name__ == '__main__':
    main()
