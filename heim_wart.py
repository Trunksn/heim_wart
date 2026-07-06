#!/usr/bin/env python3
"""
HeimWart
"""

import tkinter as tk
from tkinter import ttk
import sqlite3
from datetime import date, timedelta


class Datenbank:
    def __init__(self, db_name="heim_wart.db"):
        self.connection = sqlite3.connect(db_name)
        self.cursor = self.connection.cursor()
        self.create_table()
        self.insert_sample_data_if_empty()

    def create_table(self):
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS geraete (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                kategorie TEXT NOT NULL,
                kaufdatum TEXT NOT NULL
            )
            """
        )
        self.connection.commit()

    def insert_sample_data_if_empty(self):
        self.cursor.execute("SELECT COUNT(*) FROM geraete")
        if self.cursor.fetchone()[0] > 0:
            return
        heute = date.today()
        geraete = [
            ("Waschmaschine", "Haushalt", (heute - timedelta(days=400)).isoformat()),
            ("Gas-Heizung", "Heizungskeller", (heute - timedelta(days=800)).isoformat()),
            ("Kaffeevollautomat", "Küche", (heute - timedelta(days=200)).isoformat()),
        ]
        self.cursor.executemany(
            "INSERT INTO geraete (name, kategorie, kaufdatum) VALUES (?,?,?)", geraete
        )
        self.connection.commit()

    def get_all_geraete(self):
        self.cursor.execute("SELECT id, name, kategorie, kaufdatum FROM geraete ORDER BY name")
        return self.cursor.fetchall()

    def close(self):
        self.connection.close()


class MainApp:
    def __init__(self, root, db):
        self.root = root
        self.db = db
        self.root.title("HeimWart – Geräteübersicht")
        self.root.geometry("600x300")

        # Tabelle
        columns = ("Gerät", "Kategorie", "Kaufdatum")
        self.tree = ttk.Treeview(root, columns=columns, show="headings")
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=150)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Button zum Aktualisieren
        ttk.Button(root, text="Aktualisieren", command=self.refresh).pack(pady=5)

        self.refresh()

    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for g in self.db.get_all_geraete():
            self.tree.insert("", tk.END, values=(g[1], g[2], g[3]))


if __name__ == "__main__":
    db = Datenbank()
    root = tk.Tk()
    app = MainApp(root, db)

    def on_closing():
        db.close()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()
