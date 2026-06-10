"""
Gecmis Ekrani Frame
Onceki taramalari listeleme ve yonetme
"""

import customtkinter as ctk
from CTkTable import CTkTable
from tkinter import messagebox

from sherlock_project.storage import LocalStorage


class HistoryFrame(ctk.CTkFrame):
    """Tarama gecmisi ekrani"""

    def __init__(self, master, storage: LocalStorage, **kwargs):
        super().__init__(master, **kwargs)

        self.storage = storage
        self.scans = []

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._create_header()
        self._create_table()
        self._load_history()

    def _create_header(self):
        """Baslik bolumu"""
        self.header = ctk.CTkFrame(self, fg_color='transparent')
        self.header.grid(row=0, column=0, padx=10, pady=10, sticky='ew')

        self.title_label = ctk.CTkLabel(
            self.header,
            text='Scan History',
            font=ctk.CTkFont(size=18, weight='bold')
        )
        self.title_label.pack(side='left', padx=10)

        self.refresh_btn = ctk.CTkButton(
            self.header,
            text='Refresh',
            command=self._load_history,
            width=80
        )
        self.refresh_btn.pack(side='right', padx=10)

    def _create_table(self):
        """Gecmis tablosu"""
        self.table_frame = ctk.CTkFrame(self)
        self.table_frame.grid(row=1, column=0, padx=10, pady=10, sticky='nsew')
        self.table_frame.grid_columnconfigure(0, weight=1)
        self.table_frame.grid_rowconfigure(0, weight=1)

        headers = ['Date', 'Username', 'Results', 'Total Sites']
        self.history_table = CTkTable(
            self.table_frame, row=1, column=4,
            values=[headers],
            header_color=['#1f538d', '#1f538d'],
            hover_color=['#2b6cb0', '#2b6cb0'],
            command=self._on_row_select
        )
        self.history_table.grid(row=0, column=0, padx=10, pady=10, sticky='nsew')

        self.button_frame = ctk.CTkFrame(self.table_frame, fg_color='transparent')
        self.button_frame.grid(row=1, column=0, padx=10, pady=10, sticky='ew')

        self.delete_btn = ctk.CTkButton(
            self.button_frame,
            text='Delete Selected',
            command=self._delete_selected,
            width=120
        )
        self.delete_btn.pack(side='left', padx=5)

        self.clear_btn = ctk.CTkButton(
            self.button_frame,
            text='Clear All',
            command=self._clear_all,
            width=100,
            fg_color='#8b0000',
            hover_color='#a00000'
        )
        self.clear_btn.pack(side='right', padx=5)

    def _load_history(self):
        """Gecmisi yukle"""
        self.scans = self.storage.get_scan_history(limit=50)
        self._update_table()

    def _update_table(self):
        """Tabloyu guncelle - once temizle, sonra yeniden doldur"""
        # Mevcut satirlari temizle (header haric)
        while len(self.history_table.values) > 1:
            self.history_table.delete_row(1)

        if not self.scans:
            self.history_table.add_row(['No scan history found', '', '', ''])
            return

        for scan in self.scans:
            timestamp = scan.get('completed_at', scan.get('started_at', ''))
            if timestamp and len(timestamp) >= 16:
                timestamp = timestamp[:16]
            else:
                timestamp = 'N/A'
            username = scan.get('username', 'unknown')
            found = str(scan.get('found_count', 0))
            total = str(scan.get('total_sites', 0))

            self.history_table.add_row([timestamp, username, found, total])

    def _on_row_select(self, row_data):
        """Satir secildiginde CTkTable tarafindan cagrilir"""
        # CTkTable command callback - secilen satirdaki veriyi aliriz
        pass

    def _delete_selected(self):
        """Secili kaydi sil"""
        try:
            selected_row = self.history_table.get_selected_row()
        except Exception:
            selected_row = -1

        if selected_row is None or selected_row < 0 or selected_row == 'NONE':
            messagebox.showwarning('Warning', 'Please click on a row first to select it, then click Delete.')
            return

        # selected_row 0-indexed'dir, header satirini atlamak icin +1
        # Fakat CTkTable header'i row 0 olarak sayar, data row 1'den baslar
        # get_selected_row() da header haric data satirlarini 0-indexed doner
        idx = selected_row
        if idx < 0 or idx >= len(self.scans):
            messagebox.showerror('Error', 'Invalid row selection.')
            return

        filepath = self.scans[idx].get('_filepath', '')
        if filepath and self.storage.delete_scan(filepath):
            messagebox.showinfo('Success', 'Scan deleted successfully.')
            self._load_history()
        else:
            messagebox.showerror('Error', 'Could not delete scan.')

    def _clear_all(self):
        """Tum gecmisi sil"""
        if not messagebox.askyesno('Confirm', 'Are you sure you want to clear all history?'):
            return

        deleted = 0
        for scan in self.scans:
            filepath = scan.get('_filepath', '')
            if filepath and self.storage.delete_scan(filepath):
                deleted += 1

        messagebox.showinfo('Done', f'Deleted {deleted} scan records.')
        self._load_history()