#!/usr/bin/env python3
"""
HeimWart
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3
from datetime import date, datetime, timedelta
import calendar


def add_months(source_date, months):
    month = source_date.month - 1 + months
    year = source_date.year + month // 12
    month = month % 12 + 1
    day = min(source_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


class Datenbank:
    def __init__(self, db_name="heim_wart.db"):
        self.connection = sqlite3.connect(db_name)
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.cursor = self.connection.cursor()
        self.create_tables()
        self.init_default_categories()
        self.insert_sample_data_if_empty()

    def create_tables(self):
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
                wartungsintervall_monate INTEGER NOT NULL,
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
        self.connection.commit()

    def init_default_categories(self):
        default_cats = ["Küche", "Heizungskeller", "Sicherheit", "Fahrzeuge", "Haushalt"]
        self.cursor.execute("SELECT COUNT(*) FROM kategorien")
        if self.cursor.fetchone()[0] == 0:
            for cat in default_cats:
                self.cursor.execute("INSERT OR IGNORE INTO kategorien (name) VALUES (?)", (cat,))
            self.connection.commit()

    def insert_sample_data_if_empty(self):
        self.cursor.execute("SELECT COUNT(*) FROM geraete")
        if self.cursor.fetchone()[0] > 0:
            return
        self.cursor.execute("SELECT id, name FROM kategorien")
        kat_map = {name: cid for cid, name in self.cursor.fetchall()}
        kid = kat_map.get("Haushalt", 1)
        heute = date.today()
        g1 = ("Waschmaschine", (heute - timedelta(days=400)).isoformat(), 24, 12, kid)
        g2 = ("Gas-Heizung", (heute - timedelta(days=800)).isoformat(), 60, 12, kat_map.get("Heizungskeller", kid))
        g3 = ("Kaffeevollautomat", (heute - timedelta(days=200)).isoformat(), 12, 6, kat_map.get("Küche", kid))
        for g in (g1, g2, g3):
            self.cursor.execute(
                "INSERT INTO geraete (name, kaufdatum, garantie_monate, wartungsintervall_monate, kategorie_id) VALUES (?,?,?,?,?)",
                g,
            )
        self.connection.commit()

    # Kategorien
    def get_categories(self):
        self.cursor.execute("SELECT id, name FROM kategorien ORDER BY name")
        return self.cursor.fetchall()

    def add_category(self, name):
        try:
            self.cursor.execute("INSERT INTO kategorien (name) VALUES (?)", (name,))
            self.connection.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def delete_category(self, cat_id):
        self.cursor.execute("SELECT COUNT(*) FROM geraete WHERE kategorie_id=?", (cat_id,))
        if self.cursor.fetchone()[0] > 0:
            return False
        self.cursor.execute("DELETE FROM kategorien WHERE id=?", (cat_id,))
        self.connection.commit()
        return True

    # Geräte
    def add_geraet(self, name, kaufdatum, garantie_monate, intervall_monate, kategorie_id):
        self.cursor.execute(
            "INSERT INTO geraete (name, kaufdatum, garantie_monate, wartungsintervall_monate, kategorie_id) VALUES (?,?,?,?,?)",
            (name, kaufdatum, garantie_monate, intervall_monate, kategorie_id),
        )
        self.connection.commit()

    def update_geraet(self, geraet_id, name, kaufdatum, garantie_monate, intervall_monate, kategorie_id):
        self.cursor.execute(
            "UPDATE geraete SET name=?, kaufdatum=?, garantie_monate=?, wartungsintervall_monate=?, kategorie_id=? WHERE id=?",
            (name, kaufdatum, garantie_monate, intervall_monate, kategorie_id, geraet_id),
        )
        self.connection.commit()

    def delete_geraet(self, geraet_id):
        self.cursor.execute("DELETE FROM geraete WHERE id=?", (geraet_id,))
        self.connection.commit()

    def get_all_geraete(self):
        self.cursor.execute(
            """
            SELECT g.id, g.name, k.name, g.kaufdatum, g.garantie_monate, g.wartungsintervall_monate, g.kategorie_id
            FROM geraete g JOIN kategorien k ON g.kategorie_id = k.id
            ORDER BY g.name
            """
        )
        return self.cursor.fetchall()

    def get_geraet_by_id(self, geraet_id):
        self.cursor.execute(
            "SELECT id, name, kaufdatum, garantie_monate, wartungsintervall_monate, kategorie_id FROM geraete WHERE id=?",
            (geraet_id,),
        )
        return self.cursor.fetchone()

    # Service
    def add_service(self, geraet_id, datum, typ, beschreibung, kosten):
        self.cursor.execute(
            "INSERT INTO service_eintraege (geraet_id, datum, typ, beschreibung, kosten) VALUES (?,?,?,?,?)",
            (geraet_id, datum, typ, beschreibung, kosten),
        )
        self.connection.commit()

    # Fälligkeit
    def berechne_faelligkeit(self, geraet_id):
        geraet = self.get_geraet_by_id(geraet_id)
        if not geraet:
            return None
        kaufdatum = datetime.strptime(geraet[2], "%Y-%m-%d").date()
        intervall = geraet[4]
        self.cursor.execute(
            "SELECT datum FROM service_eintraege WHERE geraet_id=? AND typ='Wartung' ORDER BY datum DESC",
            (geraet_id,),
        )
        wartungen = self.cursor.fetchall()
        referenz = datetime.strptime(wartungen[0][0], "%Y-%m-%d").date() if wartungen else kaufdatum
        return add_months(referenz, intervall)

    def close(self):
        self.connection.close()


class KategorieDialog(tk.Toplevel):
    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = db
        self.title("Kategorien verwalten")
        self.geometry("350x300")
        self.listbox = tk.Listbox(self)
        self.listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.refresh_list()
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(btn_frame, text="Neue Kategorie", command=self.add_cat).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Löschen", command=self.delete_cat).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Schließen", command=self.destroy).pack(side=tk.RIGHT, padx=2)

    def refresh_list(self):
        self.listbox.delete(0, tk.END)
        for cid, name in self.db.get_categories():
            self.listbox.insert(tk.END, f"{name}  (ID: {cid})")

    def add_cat(self):
        name = simpledialog.askstring("Neue Kategorie", "Name:", parent=self)
        if name and name.strip():
            if self.db.add_category(name.strip()):
                self.refresh_list()
            else:
                messagebox.showwarning("Fehler", "Kategorie existiert bereits.", parent=self)

    def delete_cat(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        text = self.listbox.get(sel[0])
        try:
            cid = int(text.split("(ID:")[1].strip(" )"))
        except:
            return
        if self.db.delete_category(cid):
            self.refresh_list()
        else:
            messagebox.showwarning("Nicht möglich", "Der Kategorie sind noch Geräte zugeordnet.", parent=self)


class GeraetDialog(tk.Toplevel):
    def __init__(self, parent, db, geraet_id=None):
        super().__init__(parent)
        self.db = db
        self.geraet_id = geraet_id
        self.result = False
        self.title("Gerät bearbeiten" if geraet_id else "Neues Gerät")
        self.geometry("400x320")
        self.name_var = tk.StringVar()
        self.kaufdatum_var = tk.StringVar(value=date.today().isoformat())
        self.garantie_var = tk.IntVar(value=24)
        self.intervall_var = tk.IntVar(value=12)
        self.kategorien = self.db.get_categories()
        self.kategorie_namen = [name for _, name in self.kategorien]
        self.kategorie_id_var = tk.IntVar(value=self.kategorien[0][0] if self.kategorien else 0)
        ttk.Label(self, text="Name *:").grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)
        ttk.Entry(self, textvariable=self.name_var, width=30).grid(row=0, column=1, padx=10, pady=5)
        ttk.Label(self, text="Kategorie:").grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)
        self.cat_combo = ttk.Combobox(self, textvariable=self.kategorie_id_var, state="readonly", values=self.kategorie_namen)
        self.cat_combo.grid(row=1, column=1, padx=10, pady=5)
        if self.kategorie_namen:
            self.cat_combo.current(0)
        ttk.Label(self, text="Kaufdatum (JJJJ-MM-TT) *:").grid(row=2, column=0, sticky=tk.W, padx=10, pady=5)
        ttk.Entry(self, textvariable=self.kaufdatum_var, width=15).grid(row=2, column=1, sticky=tk.W, padx=10, pady=5)
        ttk.Label(self, text="Garantie (Monate):").grid(row=3, column=0, sticky=tk.W, padx=10, pady=5)
        ttk.Spinbox(self, from_=0, to=240, textvariable=self.garantie_var, width=8).grid(row=3, column=1, sticky=tk.W, padx=10, pady=5)
        ttk.Label(self, text="Wartungsintervall (Monate) *:").grid(row=4, column=0, sticky=tk.W, padx=10, pady=5)
        ttk.Spinbox(self, from_=1, to=120, textvariable=self.intervall_var, width=8).grid(row=4, column=1, sticky=tk.W, padx=10, pady=5)
        if geraet_id:
            g = self.db.get_geraet_by_id(geraet_id)
            if g:
                self.name_var.set(g[1])
                self.kaufdatum_var.set(g[2])
                self.garantie_var.set(g[3])
                self.intervall_var.set(g[4])
                for idx, (cid, _) in enumerate(self.kategorien):
                    if cid == g[5]:
                        self.cat_combo.current(idx)
                        break
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="Speichern", command=self.save).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="Abbrechen", command=self.destroy).pack(side=tk.LEFT, padx=10)
        self.grab_set()
        self.wait_window()

    def save(self):
        name = self.name_var.get().strip()
        kd = self.kaufdatum_var.get().strip()
        if not name or not kd:
            messagebox.showwarning("Pflichtfelder", "Name und Kaufdatum sind erforderlich.", parent=self)
            return
        try:
            datetime.strptime(kd, "%Y-%m-%d")
        except ValueError:
            messagebox.showwarning("Formatfehler", "Datum im Format JJJJ-MM-TT.", parent=self)
            return
        idx = self.cat_combo.current()
        if idx < 0:
            messagebox.showwarning("Kategorie", "Kategorie wählen.", parent=self)
            return
        kat_id = self.kategorien[idx][0]
        if self.geraet_id:
            self.db.update_geraet(self.geraet_id, name, kd, self.garantie_var.get(), self.intervall_var.get(), kat_id)
        else:
            self.db.add_geraet(name, kd, self.garantie_var.get(), self.intervall_var.get(), kat_id)
        self.result = True
        self.destroy()


class ServiceDialog(tk.Toplevel):
    def __init__(self, parent, db, geraet_id):
        super().__init__(parent)
        self.db = db
        self.geraet_id = geraet_id
        self.result = False
        self.title("Service protokollieren")
        self.geometry("400x300")
        self.typ_var = tk.StringVar(value="Wartung")
        ttk.Label(self, text="Typ:").grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)
        rb = ttk.Frame(self)
        rb.grid(row=0, column=1, sticky=tk.W)
        ttk.Radiobutton(rb, text="Wartung", variable=self.typ_var, value="Wartung").pack(side=tk.LEFT)
        ttk.Radiobutton(rb, text="Reparatur", variable=self.typ_var, value="Reparatur").pack(side=tk.LEFT)
        ttk.Label(self, text="Datum (JJJJ-MM-TT) *:").grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)
        self.datum_var = tk.StringVar(value=date.today().isoformat())
        ttk.Entry(self, textvariable=self.datum_var, width=15).grid(row=1, column=1, sticky=tk.W, padx=10, pady=5)
        ttk.Label(self, text="Beschreibung *:").grid(row=2, column=0, sticky=tk.W, padx=10, pady=5)
        self.beschr = tk.Text(self, width=30, height=4)
        self.beschr.grid(row=2, column=1, padx=10, pady=5)
        ttk.Label(self, text="Kosten (€):").grid(row=3, column=0, sticky=tk.W, padx=10, pady=5)
        self.kosten_var = tk.DoubleVar(value=0.0)
        ttk.Entry(self, textvariable=self.kosten_var, width=10).grid(row=3, column=1, sticky=tk.W, padx=10, pady=5)
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="Speichern", command=self.save).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="Abbrechen", command=self.destroy).pack(side=tk.LEFT, padx=10)
        self.grab_set()
        self.wait_window()

    def save(self):
        datum = self.datum_var.get().strip()
        beschreibung = self.beschr.get("1.0", tk.END).strip()
        if not datum or not beschreibung:
            messagebox.showwarning("Pflichtfelder", "Datum und Beschreibung sind erforderlich.", parent=self)
            return
        try:
            d = datetime.strptime(datum, "%Y-%m-%d").date()
            if d > date.today():
                messagebox.showwarning("Datum", "Datum darf nicht in der Zukunft liegen.", parent=self)
                return
        except ValueError:
            messagebox.showwarning("Formatfehler", "Datum muss JJJJ-MM-TT sein.", parent=self)
            return
        self.db.add_service(self.geraet_id, datum, self.typ_var.get(), beschreibung, self.kosten_var.get())
        self.result = True
        self.destroy()


class MainApp:
    def __init__(self, root, db):
        self.root = root
        self.db = db
        self.root.title("HeimWart – Geräteverwaltung (v0.5)")
        self.root.geometry("750x450")
        menubar = tk.Menu(root)
        root.config(menu=menubar)
        verwaltung_menu = tk.Menu(menubar, tearoff=0)
        verwaltung_menu.add_command(label="Kategorien verwalten", command=self.open_kategorie_dialog)
        menubar.add_cascade(label="Verwaltung", menu=verwaltung_menu)

        action_frame = ttk.Frame(root)
        action_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(action_frame, text="Neues Gerät", command=self.neues_geraet).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_frame, text="Gerät bearbeiten", command=self.bearbeite_geraet).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_frame, text="Gerät löschen", command=self.loesche_geraet).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_frame, text="Service eintragen", command=self.service_eintragen).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_frame, text="Aktualisieren", command=self.refresh_dashboard).pack(side=tk.LEFT, padx=2)

        columns = ("Gerät", "Kategorie", "Nächste Wartung", "Status")
        self.tree = ttk.Treeview(root, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=150)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.refresh_dashboard()

    def refresh_dashboard(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for g in self.db.get_all_geraete():
            gid, name, kat_name, kaufdatum, garantie, intervall, kat_id = g
            faellig = self.db.berechne_faelligkeit(gid)
            faellig_str = faellig.isoformat() if faellig else "?"
            heute = date.today()
            if faellig and faellig < heute:
                status = "Überfällig"
            elif faellig and faellig <= heute + timedelta(days=30):
                status = "Bald fällig"
            else:
                status = "In Ordnung"
            self.tree.insert("", tk.END, iid=str(gid), values=(name, kat_name, faellig_str, status))

    def neues_geraet(self):
        dlg = GeraetDialog(self.root, self.db)
        if dlg.result:
            self.refresh_dashboard()

    def bearbeite_geraet(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Keine Auswahl", "Bitte Gerät auswählen.", parent=self.root)
            return
        gid = int(sel[0])
        dlg = GeraetDialog(self.root, self.db, gid)
        if dlg.result:
            self.refresh_dashboard()

    def loesche_geraet(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Keine Auswahl", "Bitte Gerät auswählen.", parent=self.root)
            return
        gid = int(sel[0])
        if messagebox.askyesno("Löschen", f"Gerät {gid} wirklich löschen?", parent=self.root):
            self.db.delete_geraet(gid)
            self.refresh_dashboard()

    def service_eintragen(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Keine Auswahl", "Bitte Gerät auswählen.", parent=self.root)
            return
        gid = int(sel[0])
        dlg = ServiceDialog(self.root, self.db, gid)
        if dlg.result:
            self.refresh_dashboard()

    def open_kategorie_dialog(self):
        KategorieDialog(self.root, self.db)


if __name__ == "__main__":
    db = Datenbank()
    root = tk.Tk()
    app = MainApp(root, db)

    def on_closing():
        db.close()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()
