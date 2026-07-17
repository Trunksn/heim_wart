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
    # NFA07: Datensicherheit/Persistenz (Einsatz der transaktionssicheren SQLite-Datenbank)
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
                anschaffungskosten REAL NOT NULL DEFAULT 0.0,
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
            # NFA08: Systemsicherheit (Schutz vor SQL-Injection durch parametrisierte Abfragen '?' statt F-Strings)
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
        # NFA04: Benutzerfreundlichkeit (Logik für das visuelle Ampelsystem)
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
