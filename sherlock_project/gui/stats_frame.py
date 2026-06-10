"""
Istatistik Ekrani Frame
Tarama istatistikleri ve ozet
"""

import customtkinter as ctk

from sherlock_project.storage import LocalStorage


class StatsFrame(ctk.CTkFrame):
    """Istatistik ekrani"""

    def __init__(self, master, storage: LocalStorage, **kwargs):
        super().__init__(master, **kwargs)

        self.storage = storage

        self.grid_columnconfigure((0, 1), weight=1)
        self.grid_rowconfigure(2, weight=0)

        self._create_header()
        self._create_stats_cards()
        self._load_stats()

    def _create_header(self):
        """Baslik"""
        self.header = ctk.CTkFrame(self, fg_color='transparent')
        self.header.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky='ew')

        self.title_label = ctk.CTkLabel(
            self.header,
            text='Statistics',
            font=ctk.CTkFont(size=18, weight='bold')
        )
        self.title_label.pack(side='left', padx=10)

        self.refresh_btn = ctk.CTkButton(
            self.header,
            text='Refresh',
            command=self._load_stats,
            width=80
        )
        self.refresh_btn.pack(side='right', padx=10)

    def _create_stats_cards(self):
        """Istatistik kartlari"""
        self.cards_frame = ctk.CTkFrame(self, fg_color='transparent')
        self.cards_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky='nsew')
        self.cards_frame.grid_columnconfigure((0, 1), weight=1)

        card_data = [
            ('Total Scans', '0', '#1f538d'),
            ('Total Accounts Found', '0', '#2d6b2d'),
            ('Unique Usernames', '0', '#8b5a00'),
            ('Storage Path', '', '#4a4a4a'),
        ]

        self.value_labels = []

        for i, (title, value, color) in enumerate(card_data):
            row, col = divmod(i, 2)

            card = ctk.CTkFrame(self.cards_frame, fg_color=color, corner_radius=12)
            card.grid(row=row, column=col, padx=10, pady=10, sticky='nsew')

            title_lbl = ctk.CTkLabel(
                card,
                text=title,
                font=ctk.CTkFont(size=13),
                text_color='#ccc'
            )
            title_lbl.pack(pady=(15, 5))

            value_lbl = ctk.CTkLabel(
                card,
                text=value,
                font=ctk.CTkFont(size=28, weight='bold'),
                text_color='white',
                wraplength=180
            )
            value_lbl.pack(pady=(0, 15))

            self.value_labels.append(value_lbl)

        self.info_label = ctk.CTkLabel(
            self,
            text='Tip: Run a search first, then visit this page to see updated stats. Click Refresh to reload.',
            font=ctk.CTkFont(size=11),
            text_color='#888',
            justify='center'
        )
        self.info_label.grid(row=2, column=0, columnspan=2, padx=20, pady=(5, 10))

    def _load_stats(self):
        """Istatistikleri yukle ve kartlari guncelle"""
        stats = self.storage.get_stats()

        if len(self.value_labels) >= 4:
            self.value_labels[0].configure(text=str(stats.get('total_scans', 0)))
            self.value_labels[1].configure(text=str(stats.get('total_found_accounts', 0)))
            self.value_labels[2].configure(text=str(stats.get('unique_usernames', 0)))
            # Storage path - kisaltarak goster
            sp = stats.get('storage_path', '')
            if len(sp) > 30:
                sp = '...' + sp[-27:]
            self.value_labels[3].configure(text=sp)