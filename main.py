#!/usr/bin/env python3

"""
HeimWart: Die smarte Geräteverwaltung für Ihr Zuhause.
Autor: Niklas Gläßer (2026)

Ein Python-Skript mit grafischer Oberfläche (tkinter) und lokaler SQLite-Datenbank.
"""

import tkinter as tk
from database import Datenbank
from gui import MainApp


if __name__ == "__main__":
    # Datenbank initialisieren (wird automatisch erstellt, falls nicht vorhanden)
    db = Datenbank("heim_wart.db")

    # Hauptfenster erstellen
    root = tk.Tk()
    app = MainApp(root, db)

    def on_closing():
        db.close()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()
