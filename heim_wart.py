#!/usr/bin/env python3

"""
HeimWart: Die smarte Geräteverwaltung für Ihr Zuhause.
Autor: Niklas Gläßer (2026)

Ein Python-Skript mit grafischer Oberfläche (tkinter) und lokaler SQLite-Datenbank.
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3
from datetime import date, datetime, timedelta
import calendar


def add_months(source_date, months):
    """Addiere eine Anzahl Monate zu einem date-Objekt."""
    month = source_date.month - 1 + months
    year = source_date.year + month // 12
    month = month % 12 + 1
    day = min(source_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


class Datenbank:
    def __init__(self, db_name="heim_wart.db"):
        self.connection = sqlite3.connect(db_name)
        self.connection.execute(
            "PRAGMA foreign_keys = ON"
        )  # ON DELETE CASCADE aktivieren
        self.cursor = self.connection.cursor()
        self.create_tables()
        self.init_default_categories()
        self.insert_sample_data_if_empty()  # optionale Beispieldaten

    def create_tables(self):
        """Erstellt die Tabellen, falls sie noch nicht existieren."""
        self.cursor.executescript(
            """
            CREATE TABLE IF NOT EXISTS kategorien (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            );
            CREATE TABLE IF NOT EXISTS geraete (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                kaufdatum TEXT NOT NULL,
                garantie_monate INTEGER NOT NULL,
                wartungsintervall_monate INTEGER DEFAULT 0 NOT NULL,
                kategorie_id INTEGER NOT NULL,
                FOREIGN KEY (kategorie_id) REFERENCES kategorien(id) ON DELETE RESTRICT
            );
            CREATE TABLE IF NOT EXISTS service_eintraege (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                geraet_id INTEGER NOT NULL,
                datum TEXT NOT NULL,
                typ TEXT NOT NULL CHECK(typ IN ('Wartung', 'Reparatur')),
                beschreibung TEXT NOT NULL,
                kosten REAL DEFAULT 0.0,
                FOREIGN KEY (geraet_id) REFERENCES geraete(id) ON DELETE CASCADE
            );
        """
        )
        # Falls die Tabelle bereits existiert, aber die Spalte 'anschaffungskosten' fehlt,
        # wird sie nachträglich hinzugefügt (Standard 0.0).
        try:
            self.cursor.execute("ALTER TABLE geraete ADD COLUMN anschaffungskosten REAL NOT NULL DEFAULT 0.0")
        except sqlite3.OperationalError:
            pass  # Spalte existiert bereits

        self.connection.commit()

    def init_default_categories(self):
        """Legt Grundkategorien an, falls die Tabelle leer ist."""
        default_cats = [
            "Küche",
            "Heizungskeller",
            "Sicherheit",
            "Fahrzeuge",
            "Haushalt",
        ]
        self.cursor.execute("SELECT COUNT(*) FROM kategorien")
        if self.cursor.fetchone()[0] == 0:
            for cat in default_cats:
                self.cursor.execute(
                    "INSERT OR IGNORE INTO kategorien (name) VALUES (?)",
                    (cat,),
                )
            self.connection.commit()

    def insert_sample_data_if_empty(self):
        """Fügt Beispieldaten ein, wenn noch keine Geräte vorhanden sind (für Demonstration)."""
        self.cursor.execute("SELECT COUNT(*) FROM geraete")
        if self.cursor.fetchone()[0] > 0:
            return  # schon Daten vorhanden

        # IDs der Kategorien holen
        self.cursor.execute("SELECT id, name FROM kategorien")
        kat_map = {name: cid for cid, name in self.cursor.fetchall()}
        kid = kat_map.get("Haushalt", 1)  # Fallback

        heute = date.today()
        # Muster-Geräte (name, kaufdatum, garantie, intervall, kategorie_id, anschaffungskosten)
        g1 = (
            "Waschmaschine",
            (heute - timedelta(days=400)).isoformat(),
            24,
            12,
            kid,
            0.0,
        )
        g2 = (
            "Gas-Heizung",
            (heute - timedelta(days=800)).isoformat(),
            60,
            12,
            kat_map.get("Heizungskeller", kid),
            0.0,
        )
        g3 = (
            "Kaffeevollautomat",
            (heute - timedelta(days=200)).isoformat(),
            12,
            6,
            kat_map.get("Küche", kid),
            0.0,
        )
        self.cursor.execute(
            "INSERT INTO geraete (name, kaufdatum, garantie_monate, wartungsintervall_monate, kategorie_id, anschaffungskosten) VALUES (?,?,?,?,?,?)",
            g1,
        )
        self.cursor.execute(
            "INSERT INTO geraete (name, kaufdatum, garantie_monate, wartungsintervall_monate, kategorie_id, anschaffungskosten) VALUES (?,?,?,?,?,?)",
            g2,
        )
        self.cursor.execute(
            "INSERT INTO geraete (name, kaufdatum, garantie_monate, wartungsintervall_monate, kategorie_id, anschaffungskosten) VALUES (?,?,?,?,?,?)",
            g3,
        )
        self.connection.commit()

        # Zu den ersten beiden Geräten ein paar Services eintragen
        self.cursor.execute("SELECT id FROM geraete ORDER BY id")
        ids = [row[0] for row in self.cursor.fetchall()]
        # Waschmaschine (id1): eine Wartung vor 100 Tagen
        self.add_service(
            ids[0],
            (heute - timedelta(days=100)).isoformat(),
            "Wartung",
            "Filter gereinigt, Dichtungen geprüft",
            0.0,
        )
        # Gas-Heizung (id2): letzte Wartung vor 400 Tagen -> überfällig
        self.add_service(
            ids[1],
            (heute - timedelta(days=400)).isoformat(),
            "Wartung",
            "Jährliche Inspektion",
            120.0,
        )
        # Kaffeevollautomat (id3): noch keine Wartung -> nutzt Kaufdatum

    # ----- Kategorien -----
    def get_categories(self):
        self.cursor.execute("SELECT id, name FROM kategorien ORDER BY name")
        return self.cursor.fetchall()

    def add_category(self, name):
        try:
            self.cursor.execute(
                "INSERT INTO kategorien (name) VALUES (?)", (name,)
            )
            self.connection.commit()
            return True
        except sqlite3.IntegrityError:
            return False  # Name schon vorhanden

    def delete_category(self, cat_id):
        # Prüfen, ob Geräte dieser Kategorie zugeordnet sind
        self.cursor.execute(
            "SELECT COUNT(*) FROM geraete WHERE kategorie_id=?", (cat_id,)
        )
        if self.cursor.fetchone()[0] > 0:
            return False  # nicht löschbar, weil noch Geräte existieren
        self.cursor.execute("DELETE FROM kategorien WHERE id=?", (cat_id,))
        self.connection.commit()
        return True

    # ----- Geräte -----
    def add_geraet(
        self, name, kaufdatum, garantie_monate, intervall_monate, kategorie_id, anschaffungskosten=0.0
    ):
        self.cursor.execute(
            "INSERT INTO geraete (name, kaufdatum, garantie_monate, wartungsintervall_monate, kategorie_id, anschaffungskosten) VALUES (?,?,?,?,?,?)",
            (name, kaufdatum, garantie_monate, intervall_monate, kategorie_id, anschaffungskosten),
        )
        self.connection.commit()
        return self.cursor.lastrowid

    def update_geraet(
        self,
        geraet_id,
        name,
        kaufdatum,
        garantie_monate,
        intervall_monate,
        kategorie_id,
        anschaffungskosten=0.0,
    ):
        self.cursor.execute(
            "UPDATE geraete SET name=?, kaufdatum=?, garantie_monate=?, wartungsintervall_monate=?, kategorie_id=?, anschaffungskosten=? WHERE id=?",
            (
                name,
                kaufdatum,
                garantie_monate,
                intervall_monate,
                kategorie_id,
                anschaffungskosten,
                geraet_id,
            ),
        )
        self.connection.commit()

    def delete_geraet(self, geraet_id):
        # ON DELETE CASCADE entfernt automatisch alle Services
        self.cursor.execute("DELETE FROM geraete WHERE id=?", (geraet_id,))
        self.connection.commit()

    def get_all_geraete(self):
        query = """
            SELECT g.id, g.name, k.name, g.kaufdatum, g.garantie_monate, g.wartungsintervall_monate, g.kategorie_id
            FROM geraete g
            JOIN kategorien k ON g.kategorie_id = k.id
            ORDER BY g.name
        """
        self.cursor.execute(query)
        return self.cursor.fetchall()

    def get_geraet_by_id(self, geraet_id):
        self.cursor.execute(
            "SELECT id, name, kaufdatum, garantie_monate, wartungsintervall_monate, kategorie_id, anschaffungskosten FROM geraete WHERE id=?",
            (geraet_id,),
        )
        return self.cursor.fetchone()

    # ----- Service-Einträge -----
    def add_service(self, geraet_id, datum, typ, beschreibung, kosten):
        self.cursor.execute(
            "INSERT INTO service_eintraege (geraet_id, datum, typ, beschreibung, kosten) VALUES (?,?,?,?,?)",
            (geraet_id, datum, typ, beschreibung, kosten),
        )
        self.connection.commit()

    def get_service_history(self, geraet_id):
        self.cursor.execute(
            "SELECT id, datum, typ, beschreibung, kosten FROM service_eintraege WHERE geraet_id=? ORDER BY datum DESC",
            (geraet_id,),
        )
        return self.cursor.fetchall()

    # ----- Fälligkeitsberechnung -----
    def berechne_faelligkeit(self, geraet_id):
        """Berechnet das nächste Fälligkeitsdatum für ein Gerät.
        Liefert None, wenn kein Wartungsintervall definiert ist (Intervall = 0)."""
        geraet = self.get_geraet_by_id(geraet_id)
        if not geraet:
            return None
        # Entpacken mit neuer Spaltenstruktur (id, name, kaufdatum, garantie, intervall, kategorie_id, anschaffungskosten)
        _, name, kaufdatum_str, _, intervall, _, _ = geraet
        if intervall is None or intervall == 0:
            return None  # Kein Intervall festgelegt

        kaufdatum = datetime.strptime(kaufdatum_str, "%Y-%m-%d").date()

        # Alle Wartungen (nicht Reparaturen) laden, nach Datum absteigend
        self.cursor.execute(
            "SELECT datum FROM service_eintraege WHERE geraet_id=? AND typ='Wartung' ORDER BY datum DESC",
            (geraet_id,),
        )
        wartungen = self.cursor.fetchall()
        if wartungen:
            letzte_wartung = datetime.strptime(
                wartungen[0][0], "%Y-%m-%d"
            ).date()
            referenz = letzte_wartung
        else:
            referenz = kaufdatum

        faellig = add_months(referenz, intervall)
        return faellig

    def get_status(self, geraet_id):
        """Gibt Status-String und Farbcode zurück."""
        faellig = self.berechne_faelligkeit(geraet_id)
        if faellig is None:
            return "Kein Intervall", "gray"
        heute = date.today()
        if faellig < heute:
            return "Überfällig", "red"
        elif faellig <= heute + timedelta(days=30):
            return "Bald fällig", "orange"
        else:
            return "In Ordnung", "green"

    def close(self):
        self.connection.close()


class KategorieDialog(tk.Toplevel):
    """Fenster zum Verwalten von Kategorien."""

    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = db
        self.title("Kategorien verwalten")
        self.geometry("350x300")
        self.resizable(True, True)

        self.listbox = tk.Listbox(self)
        self.listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.refresh_list()

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(
            btn_frame, text="Neue Kategorie", command=self.add_cat
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Löschen", command=self.delete_cat).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(btn_frame, text="Schließen", command=self.destroy).pack(
            side=tk.RIGHT, padx=2
        )

    def refresh_list(self):
        self.listbox.delete(0, tk.END)
        for cid, name in self.db.get_categories():
            self.listbox.insert(tk.END, f"{name}  (ID: {cid})")

    def add_cat(self):
        name = simpledialog.askstring(
            "Neue Kategorie", "Name der neuen Kategorie:", parent=self
        )
        if name and name.strip():
            if self.db.add_category(name.strip()):
                self.refresh_list()
            else:
                messagebox.showwarning(
                    "Fehler",
                    "Kategorie existiert bereits oder konnte nicht angelegt werden.",
                    parent=self,
                )

    def delete_cat(self):
        sel = self.listbox.curselection()
        if not sel:
            messagebox.showinfo(
                "Keine Auswahl",
                "Bitte wählen Sie eine Kategorie aus.",
                parent=self,
            )
            return
        text = self.listbox.get(sel[0])
        # ID extrahieren (Annahme: Format "Name  (ID: 123)")
        try:
            cid = int(text.split("(ID:")[1].strip(" )"))
        except:
            return
        if self.db.delete_category(cid):
            self.refresh_list()
        else:
            messagebox.showwarning(
                "Nicht möglich",
                "Diese Kategorie kann nicht gelöscht werden, weil ihr noch Geräte zugeordnet sind.",
                parent=self,
            )


class GeraetDialog(tk.Toplevel):
    """Dialog zum Anlegen oder Bearbeiten eines Geräts."""

    def __init__(self, parent, db, geraet_id=None):
        super().__init__(parent)
        self.db = db
        self.geraet_id = geraet_id
        self.result = None  # wird True, wenn erfolgreich gespeichert

        if geraet_id:
            self.title("Gerät bearbeiten")
        else:
            self.title("Neues Gerät anlegen")
        self.geometry("400x380")  # etwas höher für das neue Feld
        self.resizable(False, False)

        # Variablen
        self.name_var = tk.StringVar()
        self.kaufdatum_var = tk.StringVar(value=date.today().isoformat())
        self.garantie_var = tk.IntVar(value=24)
        self.intervall_var = tk.IntVar(value=0)  # 0 = kein Intervall
        self.kategorie_id_var = tk.IntVar()
        self.anschaffungskosten_var = tk.DoubleVar(value=0.0)

        # Kategorien laden
        self.kategorien = self.db.get_categories()
        self.kategorie_namen = [name for _, name in self.kategorien]
        if self.kategorien:
            self.kategorie_id_var.set(self.kategorien[0][0])

        # Widgets
        ttk.Label(self, text="Name *:").grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=5
        )
        ttk.Entry(self, textvariable=self.name_var, width=30).grid(
            row=0, column=1, padx=10, pady=5
        )

        ttk.Label(self, text="Kategorie:").grid(
            row=1, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.cat_combo = ttk.Combobox(
            self,
            textvariable=self.kategorie_id_var,
            state="readonly",
            values=self.kategorie_namen,
        )
        self.cat_combo.grid(row=1, column=1, padx=10, pady=5)
        if self.kategorie_namen:
            self.cat_combo.current(0)

        ttk.Label(self, text="Kaufdatum (JJJJ-MM-TT) *:").grid(
            row=2, column=0, sticky=tk.W, padx=10, pady=5
        )
        ttk.Entry(self, textvariable=self.kaufdatum_var, width=15).grid(
            row=2, column=1, sticky=tk.W, padx=10, pady=5
        )

        ttk.Label(self, text="Garantie (Monate):").grid(
            row=3, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.garantie_spin = ttk.Spinbox(
            self, from_=0, to=240, textvariable=self.garantie_var, width=8
        )
        self.garantie_spin.grid(row=3, column=1, sticky=tk.W, padx=10, pady=5)

        # Wartungsintervall jetzt optional (0 = kein Intervall)
        ttk.Label(self, text="Wartungsintervall (Monate, optional):").grid(
            row=4, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.intervall_spin = ttk.Spinbox(
            self, from_=0, to=120, textvariable=self.intervall_var, width=8
        )
        self.intervall_spin.grid(row=4, column=1, sticky=tk.W, padx=10, pady=5)

        ttk.Label(self, text="Anschaffungskosten (€):").grid(
            row=5, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.anschaffungskosten_entry = ttk.Entry(self, textvariable=self.anschaffungskosten_var, width=10)
        self.anschaffungskosten_entry.grid(row=5, column=1, sticky=tk.W, padx=10, pady=5)

        # Vorbelegung, falls Bearbeiten
        if geraet_id:
            geraet = self.db.get_geraet_by_id(geraet_id)
            if geraet:
                # geraet = (id, name, kaufdatum, garantie, intervall, kategorie_id, anschaffungskosten)
                self.name_var.set(geraet[1])
                self.kaufdatum_var.set(geraet[2])
                self.garantie_var.set(geraet[3])
                self.intervall_var.set(geraet[4])
                self.anschaffungskosten_var.set(geraet[6])
                # passende Kategorie auswählen
                for idx, (cid, name) in enumerate(self.kategorien):
                    if cid == geraet[5]:
                        self.cat_combo.current(idx)
                        break

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=6, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="Speichern", command=self.save).pack(
            side=tk.LEFT, padx=10
        )
        ttk.Button(btn_frame, text="Abbrechen", command=self.destroy).pack(
            side=tk.LEFT, padx=10
        )

        self.grab_set()  # Modal
        self.wait_window()

    def save(self):
        name = self.name_var.get().strip()
        kaufdatum_str = self.kaufdatum_var.get().strip()
        if not name or not kaufdatum_str:
            messagebox.showwarning(
                "Pflichtfelder",
                "Name und Kaufdatum müssen ausgefüllt werden.",
                parent=self,
            )
            return
        try:
            datetime.strptime(kaufdatum_str, "%Y-%m-%d")
        except ValueError:
            messagebox.showwarning(
                "Formatfehler",
                "Das Kaufdatum muss im Format JJJJ-MM-TT sein (z.B. 2025-01-15).",
                parent=self,
            )
            return

        # Validierung Garantie (nur Ganzzahl)
        garantie_text = self.garantie_spin.get().strip()
        if not garantie_text.isdigit():
            messagebox.showwarning(
                "Ungültige Eingabe",
                "Garantie muss eine ganze Zahl sein.",
                parent=self,
            )
            return
        garantie = int(garantie_text)

        # Validierung Wartungsintervall (nur Ganzzahl)
        intervall_text = self.intervall_spin.get().strip()
        if not intervall_text.isdigit():
            messagebox.showwarning(
                "Ungültige Eingabe",
                "Wartungsintervall muss eine ganze Zahl sein.",
                parent=self,
            )
            return
        intervall = int(intervall_text)

        # Validierung der Anschaffungskosten (nur Zahlen erlaubt)
        anschaffung_str = self.anschaffungskosten_entry.get().strip()
        if not anschaffung_str:
            anschaffung_str = "0"
        try:
            anschaffung = float(anschaffung_str)
        except ValueError:
            messagebox.showwarning(
                "Ungültige Eingabe",
                "Anschaffungskosten müssen eine Zahl sein.",
                parent=self,
            )
            return

        # Kategorie-ID aus Combobox ermitteln
        selected_idx = self.cat_combo.current()
        if selected_idx < 0:
            messagebox.showwarning(
                "Kategorie",
                "Bitte wählen Sie eine Kategorie aus.",
                parent=self,
            )
            return
        kat_id = self.kategorien[selected_idx][0]

        if self.geraet_id:  # Update
            self.db.update_geraet(
                self.geraet_id,
                name,
                kaufdatum_str,
                garantie,
                intervall,
                kat_id,
                anschaffung,
            )
        else:
            self.db.add_geraet(
                name, kaufdatum_str, garantie, intervall, kat_id, anschaffung
            )

        self.result = True
        self.destroy()


class ServiceDialog(tk.Toplevel):
    """Dialog zum Protokollieren einer neuen Wartung oder Reparatur."""

    def __init__(self, parent, db, geraet_id):
        super().__init__(parent)
        self.db = db
        self.geraet_id = geraet_id
        self.result = False

        self.title("Neuen Serviceeintrag protokollieren")
        self.geometry("420x300")
        self.resizable(False, False)

        # Typ-Auswahl
        self.typ_var = tk.StringVar(value="Wartung")
        ttk.Label(self, text="Typ:").grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=5
        )
        rb_frame = ttk.Frame(self)
        rb_frame.grid(row=0, column=1, sticky=tk.W)
        ttk.Radiobutton(
            rb_frame, text="Wartung", variable=self.typ_var, value="Wartung"
        ).pack(side=tk.LEFT)
        ttk.Radiobutton(
            rb_frame,
            text="Reparatur",
            variable=self.typ_var,
            value="Reparatur",
        ).pack(side=tk.LEFT)

        # Datum
        ttk.Label(self, text="Datum (JJJJ-MM-TT) *:").grid(
            row=1, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.datum_var = tk.StringVar(value=date.today().isoformat())
        ttk.Entry(self, textvariable=self.datum_var, width=15).grid(
            row=1, column=1, sticky=tk.W, padx=10, pady=5
        )

        # Beschreibung
        ttk.Label(self, text="Beschreibung *:").grid(
            row=2, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.beschreibung_text = tk.Text(self, width=30, height=4)
        self.beschreibung_text.grid(row=2, column=1, padx=10, pady=5)

        # Kosten
        ttk.Label(self, text="Kosten (€, optional):").grid(
            row=3, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.kosten_var = tk.DoubleVar(value=0.0)
        self.kosten_entry = ttk.Entry(self, textvariable=self.kosten_var, width=10)
        self.kosten_entry.grid(row=3, column=1, sticky=tk.W, padx=10, pady=5)

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="Speichern", command=self.save).pack(
            side=tk.LEFT, padx=10
        )
        ttk.Button(btn_frame, text="Abbrechen", command=self.destroy).pack(
            side=tk.LEFT, padx=10
        )

        self.grab_set()
        self.wait_window()

    def save(self):
        datum_str = self.datum_var.get().strip()
        typ = self.typ_var.get()
        beschreibung = self.beschreibung_text.get("1.0", tk.END).strip()

        # Validierung der Kosten (nur Zahlen erlaubt)
        kosten_str = self.kosten_entry.get().strip()
        if not kosten_str:
            kosten_str = "0"
        try:
            kosten = float(kosten_str)
        except ValueError:
            messagebox.showwarning(
                "Ungültige Eingabe",
                "Kosten müssen eine Zahl sein.",
                parent=self,
            )
            return

        # Validierung von Datum und Beschreibung
        if not datum_str or not beschreibung:
            messagebox.showwarning(
                "Pflichtfelder",
                "Datum und Beschreibung sind erforderlich.",
                parent=self,
            )
            return
        try:
            datum = datetime.strptime(datum_str, "%Y-%m-%d").date()
            if datum > date.today():
                messagebox.showwarning(
                    "Datum",
                    "Das Datum darf nicht in der Zukunft liegen.",
                    parent=self,
                )
                return
        except ValueError:
            messagebox.showwarning(
                "Formatfehler", "Datum muss JJJJ-MM-TT sein.", parent=self
            )
            return

        self.db.add_service(
            self.geraet_id, datum_str, typ, beschreibung, kosten
        )
        self.result = True
        self.destroy()


class DetailDialog(tk.Toplevel):
    """Zeigt die Service-Historie eines Geräts und ermöglicht neue Einträge."""

    def __init__(self, parent, db, geraet_id):
        super().__init__(parent)
        self.db = db
        self.geraet_id = geraet_id
        self.title("Gerätedetails & Historie")
        self.geometry("600x400")

        geraet = self.db.get_geraet_by_id(geraet_id)
        if not geraet:
            self.destroy()
            return

        # geraet = (id, name, kaufdatum, garantie, intervall, kategorie_id, anschaffungskosten)
        name, kaufdatum, garantie, intervall, kat_id, anschaffung = (
            geraet[1],
            geraet[2],
            geraet[3],
            geraet[4],
            geraet[5],
            geraet[6],
        )
        # Kategorienamen ermitteln
        kat_name = ""
        for cid, cname in self.db.get_categories():
            if cid == kat_id:
                kat_name = cname
                break

        info_frame = ttk.Frame(self)
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(
            info_frame,
            text=f"Gerät: {name}",
            font=("TkDefaultFont", 10, "bold"),
        ).pack(anchor=tk.W)
        ttk.Label(
            info_frame,
            text=f"Kategorie: {kat_name}  |  Kaufdatum: {kaufdatum}  |  Wartungsintervall: {intervall if intervall else 'keins'}  |  Anschaffung: {anschaffung:.2f} €",
        ).pack(anchor=tk.W)

        # Historie Treeview
        columns = ("Datum", "Typ", "Beschreibung", "Kosten")
        self.tree = ttk.Treeview(
            self, columns=columns, show="headings", height=10
        )
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=130 if col != "Beschreibung" else 200)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.refresh_history()

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(
            btn_frame, text="Neuer Serviceeintrag", command=self.neuer_service
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Schließen", command=self.destroy).pack(
            side=tk.RIGHT, padx=5
        )

    def refresh_history(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for entry in self.db.get_service_history(self.geraet_id):
            # entry = (id, datum, typ, beschreibung, kosten)
            self.tree.insert(
                "",
                tk.END,
                values=(
                    entry[1],
                    entry[2],
                    entry[3],
                    f"{entry[4]:.2f} €" if entry[4] else "",
                ),
            )

    def neuer_service(self):
        dialog = ServiceDialog(self, self.db, self.geraet_id)
        if dialog.result:
            self.refresh_history()
            # auch das Hauptfenster aktualisieren (Dashboard), falls offen
            if hasattr(self.master, "refresh_dashboard"):
                self.master.refresh_dashboard()


class MainApp:
    """Hauptfenster der Anwendung."""

    def __init__(self, root, db):
        self.root = root
        self.db = db
        self.root.title("HeimWart – Geräteverwaltung")
        self.root.geometry("800x550")
        self.root.minsize(600, 450)

        # Menüleiste
        menubar = tk.Menu(root)
        root.config(menu=menubar)
        datei_menu = tk.Menu(menubar, tearoff=0)
        datei_menu.add_command(label="Beenden", command=root.quit)
        menubar.add_cascade(label="Datei", menu=datei_menu)
        verwaltung_menu = tk.Menu(menubar, tearoff=0)
        verwaltung_menu.add_command(
            label="Kategorien verwalten", command=self.open_kategorie_dialog
        )
        menubar.add_cascade(label="Verwaltung", menu=verwaltung_menu)
        hilfe_menu = tk.Menu(menubar, tearoff=0)
        hilfe_menu.add_command(label="Über", command=self.show_about)
        menubar.add_cascade(label="Hilfe", menu=hilfe_menu)

        # Oberes Button-Frame für Aktionen
        action_frame = ttk.Frame(root)
        action_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(
            action_frame, text="Neues Gerät", command=self.neues_geraet
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(
            action_frame,
            text="Gerät bearbeiten",
            command=self.bearbeite_geraet,
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(
            action_frame, text="Gerät löschen", command=self.loesche_geraet
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(
            action_frame,
            text="Service eintragen",
            command=self.service_eintragen,
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(
            action_frame,
            text="Dashboard aktualisieren",
            command=self.refresh_dashboard,
        ).pack(side=tk.LEFT, padx=2)

        # --- Filterleiste (Such- und Kategoriefilter) ---
        filter_frame = ttk.Frame(root)
        filter_frame.pack(fill=tk.X, padx=10, pady=(5, 0))

        ttk.Label(filter_frame, text="Filter:").pack(side=tk.LEFT)
        self.filter_category_var = tk.StringVar()
        self.filter_category_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.filter_category_var,
            state="readonly",
            width=18,
        )
        self.filter_category_combo.pack(side=tk.LEFT, padx=5)
        self.filter_category_combo.bind(
            "<<ComboboxSelected>>", lambda e: self.refresh_dashboard()
        )

        ttk.Label(filter_frame, text="Suche:").pack(side=tk.LEFT, padx=(10, 0))
        self.filter_search_var = tk.StringVar()
        self.filter_search_entry = ttk.Entry(
            filter_frame, textvariable=self.filter_search_var, width=20
        )
        self.filter_search_entry.pack(side=tk.LEFT, padx=5)
        self.filter_search_entry.bind(
            "<KeyRelease>", lambda e: self.refresh_dashboard()
        )

        # initialen Kategoriefilter befüllen
        self.kategorien_liste = []  # wird in update_category_filter() gesetzt
        self.update_category_filter()

        # Dashboard als Treeview mit farbigen Status-Zeilen
        self.columns = ("Gerät", "Kategorie", "Nächste Wartung", "Status")
        self.tree = ttk.Treeview(
            root, columns=self.columns, show="headings", selectmode="browse"
        )
        for col in self.columns:
            self.tree.heading(col, text=col)
            self.tree.column(
                col, width=150 if col != "Nächste Wartung" else 170
            )
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Tags für die Statusfarben
        self.tree.tag_configure("red", background="#f8d7da")  # hellrot
        self.tree.tag_configure("orange", background="#fff3cd")  # gelb
        self.tree.tag_configure("green", background="#d4edda")  # grün
        self.tree.tag_configure("gray", background="#e2e3e5")  # grau für "Kein Intervall"

        # Doppelklick öffnet Detailansicht
        self.tree.bind("<Double-1>", self.on_double_click)

        self.refresh_dashboard()
        # Warnung beim Start, falls Geräte überfällig sind
        self.warn_overdue()

    def update_category_filter(self):
        """Aktualisiert die Kategorienliste im Dropdown-Filter."""
        kats = self.db.get_categories()
        self.kategorien_liste = kats
        werte = ["Alle Kategorien"] + [name for _, name in kats]
        aktuell = self.filter_category_var.get()
        self.filter_category_combo["values"] = werte
        if aktuell in werte:
            self.filter_category_var.set(aktuell)
        else:
            self.filter_category_var.set("Alle Kategorien")

    def warn_overdue(self):
        """Prüft alle Geräte und zeigt ein einziges Popup mit allen überfälligen Wartungen an."""
        geraete = self.db.get_all_geraete()
        overdue = []
        for g in geraete:
            gid = g[0]
            status_text, _ = self.db.get_status(gid)
            if status_text == "Überfällig":
                name = g[1]
                faellig = self.db.berechne_faelligkeit(gid)
                faellig_str = faellig.isoformat() if faellig else "?"
                overdue.append(f"- {name} (fällig seit {faellig_str})")
        if overdue:
            msg = "Folgende Geräte sind überfällig:\n\n" + "\n".join(overdue)
            messagebox.showwarning("Überfällige Wartungen", msg, parent=self.root)

    def refresh_dashboard(self):
        """Liest alle Geräte aus der DB, wendet Filter an und aktualisiert die Dashboard-Liste."""
        for row in self.tree.get_children():
            self.tree.delete(row)

        geraete = self.db.get_all_geraete()

        # 1) Kategoriefilter
        selected_cat = self.filter_category_var.get()
        if selected_cat and selected_cat != "Alle Kategorien":
            # ID der gewählten Kategorie finden
            kat_id = None
            for cid, cname in self.kategorien_liste:
                if cname == selected_cat:
                    kat_id = cid
                    break
            if kat_id is not None:
                geraete = [g for g in geraete if g[6] == kat_id]  # g[6] = kategorie_id

        # 2) Textsuche (Gerätename)
        search_text = self.filter_search_var.get().strip().lower()
        if search_text:
            geraete = [g for g in geraete if search_text in g[1].lower()]  # g[1] = name

        # Sortierung: nach nächster fälliger Wartung (früheste zuerst), Geräte ohne Intervall am Ende
        def sort_key(g):
            faellig = self.db.berechne_faelligkeit(g[0])  # g[0] = Geräte-ID
            if faellig is None:
                return (date.max, g[1].lower())   # date.max ganz nach hinten
            else:
                return (faellig, g[1].lower())
        geraete.sort(key=sort_key)

        for g in geraete:
            gid, name, kat_name, kaufdatum, garantie, intervall, kat_id = g
            faellig = self.db.berechne_faelligkeit(gid)
            faellig_str = faellig.isoformat() if faellig else "—"
            status_text, color = self.db.get_status(gid)

            # Geräte ohne Wartungsintervall erhalten keine Hintergrundfarbe
            if color == "gray":
                self.tree.insert(
                    "",
                    tk.END,
                    iid=str(gid),
                    values=(name, kat_name, faellig_str, status_text),
                )
            else:
                self.tree.insert(
                    "",
                    tk.END,
                    iid=str(gid),
                    values=(name, kat_name, faellig_str, status_text),
                    tags=(color,),
                )

    def neues_geraet(self):
        dialog = GeraetDialog(self.root, self.db)
        if dialog.result:
            self.refresh_dashboard()

    def bearbeite_geraet(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo(
                "Keine Auswahl",
                "Bitte wählen Sie ein Gerät aus der Liste.",
                parent=self.root,
            )
            return
        gid = int(selected[0])
        dialog = GeraetDialog(self.root, self.db, gid)
        if dialog.result:
            self.refresh_dashboard()

    def loesche_geraet(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo(
                "Keine Auswahl",
                "Bitte wählen Sie ein Gerät aus.",
                parent=self.root,
            )
            return
        gid = int(selected[0])
        if messagebox.askyesno(
            "Löschen bestätigen",
            f"Soll das Gerät (ID {gid}) und alle zugehörigen Serviceeinträge wirklich gelöscht werden?",
            parent=self.root,
        ):
            self.db.delete_geraet(gid)
            self.refresh_dashboard()

    def service_eintragen(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo(
                "Keine Auswahl",
                "Bitte wählen Sie ein Gerät aus, für das Sie einen Service protokollieren möchten.",
                parent=self.root,
            )
            return
        gid = int(selected[0])
        dialog = ServiceDialog(self.root, self.db, gid)
        if dialog.result:
            self.refresh_dashboard()

    def on_double_click(self, event):
        selected = self.tree.selection()
        if selected:
            gid = int(selected[0])
            detail = DetailDialog(self.root, self.db, gid)
            # Nach Schließen des Detaildialogs das Dashboard aktualisieren
            self.root.wait_window(detail)
            self.refresh_dashboard()

    def open_kategorie_dialog(self):
        KategorieDialog(self.root, self.db)
        # Nach dem Schließen des Dialogs den Filter aktualisieren, 
        # falls Kategorien hinzugefügt oder gelöscht wurden.
        self.update_category_filter()

    def show_about(self):
        messagebox.showinfo(
            "Über HeimWart\n",
            "Die smarte Geräteverwaltung für Ihr Zuhause.\n"
            "Version 1.0\n\n"
            "Entwickelt im Rahmen des Portfoliokurses.",
            parent=self.root,
        )


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
