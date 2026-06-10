"""
Arama Ekrani Frame
Kullanici adi arama ve sonuc gosterimi
"""

import customtkinter as ctk
from CTkTable import CTkTable
import asyncio
import threading
from typing import Callable, List
from datetime import datetime

from sherlock_project.sites import SitesInformation
from sherlock_project.storage import LocalStorage
from sherlock_project.async_sherlock import AsyncSherlock, ScanConfig
from sherlock_project.result import QueryStatus
from sherlock_project.reporting import PDFExporter, ExcelExporter, HTMLExporter
import subprocess
import os


class SearchFrame(ctk.CTkFrame):
    """Ana arama ekrani"""

    def __init__(
        self,
        master,
        sites: SitesInformation,
        storage: LocalStorage,
        on_results: Callable = None,
        **kwargs
    ):
        super().__init__(master, **kwargs)

        self.sites = sites
        self.storage = storage
        self.on_results = on_results
        self.results = []
        self.is_scanning = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._create_search_section()
        self._create_options_section()
        self._create_results_section()

    def _create_search_section(self):
        """Arama bolumu"""
        self.search_frame = ctk.CTkFrame(self)
        self.search_frame.grid(row=0, column=0, padx=10, pady=10, sticky='ew')
        self.search_frame.grid_columnconfigure(1, weight=1)

        self.username_label = ctk.CTkLabel(
            self.search_frame,
            text='Username:',
            font=ctk.CTkFont(size=14, weight='bold')
        )
        self.username_label.grid(row=0, column=0, padx=10, pady=10)

        self.username_entry = ctk.CTkEntry(
            self.search_frame,
            placeholder_text='Enter username to search...',
            height=40,
            font=ctk.CTkFont(size=14)
        )
        self.username_entry.grid(row=0, column=1, padx=10, pady=10, sticky='ew')
        self.username_entry.bind('<Return>', lambda e: self._start_search())

        self.search_btn = ctk.CTkButton(
            self.search_frame,
            text='Search',
            command=self._start_search,
            height=40,
            width=120,
            font=ctk.CTkFont(size=14, weight='bold')
        )
        self.search_btn.grid(row=0, column=2, padx=10, pady=10)

        self.progress_bar = ctk.CTkProgressBar(self.search_frame)
        self.progress_bar.grid(row=1, column=0, columnspan=3, padx=10, pady=5, sticky='ew')
        self.progress_bar.set(0)

        self.progress_label = ctk.CTkLabel(
            self.search_frame,
            text='Ready',
            font=ctk.CTkFont(size=11)
        )
        self.progress_label.grid(row=2, column=0, columnspan=3, pady=(0, 5))

    def _create_options_section(self):
        """Secenekler bolumu"""
        self.options_frame = ctk.CTkFrame(self)
        self.options_frame.grid(row=1, column=0, padx=10, pady=5, sticky='ew')

        self.sites_label = ctk.CTkLabel(
            self.options_frame,
            text=f'Sites: {len(self.sites)} total'
        )
        self.sites_label.pack(side='left', padx=10)

        self.concurrent_var = ctk.IntVar(value=20)
        self.concurrent_label = ctk.CTkLabel(self.options_frame, text='Concurrent:')
        self.concurrent_label.pack(side='left', padx=(20, 5))
        self.concurrent_slider = ctk.CTkSlider(
            self.options_frame, from_=5, to=50, number_of_steps=9,
            variable=self.concurrent_var, width=100
        )
        self.concurrent_slider.pack(side='left')
        self.concurrent_value = ctk.CTkLabel(self.options_frame, text='20')
        self.concurrent_value.pack(side='left', padx=5)
        self.concurrent_slider.configure(command=lambda v: self.concurrent_value.configure(text=f'{int(v)}'))

        self.timeout_var = ctk.StringVar(value='10.0')
        self.timeout_label = ctk.CTkLabel(self.options_frame, text='Timeout (s):')
        self.timeout_label.pack(side='left', padx=(20, 5))
        self.timeout_entry = ctk.CTkEntry(self.options_frame, width=50, textvariable=self.timeout_var)
        self.timeout_entry.pack(side='left')

    def _create_results_section(self):
        """Sonuclar bolumu"""
        self.results_frame = ctk.CTkFrame(self)
        self.results_frame.grid(row=2, column=0, padx=10, pady=10, sticky='nsew')
        self.results_frame.grid_columnconfigure(0, weight=1)
        self.results_frame.grid_rowconfigure(0, weight=1)

        headers = ['Site', 'Status', 'Response Time', 'URL']
        self.results_table = CTkTable(
            self.results_frame, row=0, column=4,
            values=[headers],
            header_color=['#1f538d', '#1f538d'],
            hover_color=['#2b6cb0', '#2b6cb0']
        )
        self.results_table.grid(row=0, column=0, padx=10, pady=10, sticky='nsew')

        self.button_frame = ctk.CTkFrame(self.results_frame, fg_color='transparent')
        self.button_frame.grid(row=1, column=0, padx=10, pady=10, sticky='ew')

        self.export_pdf_btn = ctk.CTkButton(
            self.button_frame, text='Export PDF',
            command=lambda: self._export('pdf'), width=100
        )
        self.export_pdf_btn.pack(side='left', padx=5)

        self.export_excel_btn = ctk.CTkButton(
            self.button_frame, text='Export Excel',
            command=lambda: self._export('excel'), width=100
        )
        self.export_excel_btn.pack(side='left', padx=5)

        self.export_html_btn = ctk.CTkButton(
            self.button_frame, text='Export HTML',
            command=lambda: self._export('html'), width=100
        )
        self.export_html_btn.pack(side='left', padx=5)

        self.summary_label = ctk.CTkLabel(
            self.button_frame, text='Found: 0 | Checked: 0',
            font=ctk.CTkFont(size=12)
        )
        self.summary_label.pack(side='right', padx=10)

    def _start_search(self):
        """Aramayi baslat"""
        username = self.username_entry.get().strip()
        if not username:
            self.progress_label.configure(text='Please enter a username', text_color='red')
            return
        if self.is_scanning:
            return

        self.is_scanning = True
        self.search_btn.configure(state='disabled', text='Searching...')
        self.results = []

        thread = threading.Thread(target=self._run_scan, args=(username,))
        thread.daemon = True
        thread.start()

    def _run_scan(self, username: str):
        """Async tarama calistir"""
        asyncio.run(self._scan_async(username))

    async def _scan_async(self, username: str):
        """Asenkron tarama"""
        try:
            timeout = float(self.timeout_var.get())
        except ValueError:
            timeout = 10.0

        config = ScanConfig(
            max_concurrent=self.concurrent_var.get(),
            timeout=timeout
        )

        def progress_callback(completed, total, result):
            progress = completed / total
            self.after(0, lambda: self._update_progress(progress, completed, total, result))

        try:
            async with AsyncSherlock(self.sites, config) as scanner:
                self.results = await scanner.scan(username, progress_callback=progress_callback)

            await self.storage.save_scan(username, self.results, len(self.sites))
            self.after(0, self._scan_complete)
        except Exception as e:
            self.after(0, lambda: self._scan_error(str(e)))

    def _update_progress(self, progress: float, completed: int, total: int, result):
        """Ilerleme guncelle"""
        self.progress_bar.set(progress)
        self.progress_label.configure(
            text=f'Checking: {result.site_name} ({completed}/{total})',
            text_color='white'
        )
        if result.status == QueryStatus.CLAIMED:
            self._add_result_to_table(result)
        found = sum(1 for r in self.results if r.status == QueryStatus.CLAIMED)
        self.summary_label.configure(text=f'Found: {found} | Checked: {completed}')

    def _add_result_to_table(self, result):
        """Sonucu tabloya ekle"""
        row_data = [
            result.site_name,
            'Found',
            f'{result.query_time:.2f}s',
            result.site_url_user
        ]
        self.results_table.add_row(row_data)

    def _scan_complete(self):
        """Tarama tamamlandi"""
        self.is_scanning = False
        self.search_btn.configure(state='normal', text='Search')
        self.progress_label.configure(text='Scan complete!', text_color='green')
        if self.on_results:
            self.on_results(self.results)

    def _scan_error(self, error: str):
        """Tarama hatasi"""
        self.is_scanning = False
        self.search_btn.configure(state='normal', text='Search')
        self.progress_label.configure(text=f'Error: {error}', text_color='red')

    def _export(self, format_type: str):
        """Sonuclari disa aktar"""
        if not self.results:
            self.progress_label.configure(text='No results to export', text_color='orange')
            return

        username = self.username_entry.get().strip()
        if not username:
            username = "unknown"

        try:
            output_path = None
            if format_type == 'pdf':
                output_path = PDFExporter.export(self.results, username)
            elif format_type == 'excel':
                output_path = ExcelExporter.export(self.results, username)
            elif format_type == 'html':
                output_path = HTMLExporter.export(self.results, username)

            if output_path:
                self.progress_label.configure(
                    text=f'Exported to {output_path}',
                    text_color='green'
                )
                # Try to open the file
                try:
                    if os.name == 'nt':  # Windows
                        os.startfile(output_path)
                    else:  # Linux/Mac
                        subprocess.run(['xdg-open', output_path], check=False)
                except Exception:
                    pass
        except Exception as e:
            self.progress_label.configure(
                text=f'Export error: {str(e)}',
                text_color='red'
            )
