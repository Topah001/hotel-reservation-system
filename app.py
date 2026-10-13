"""Local hotel room availability and reservation manager."""
from datetime import date
import sqlite3
from contextlib import contextmanager

ROOM_SEEDS = (("101", "Standard Queen", 2, 12900), ("102", "Standard Queen", 2, 12900),
              ("201", "Deluxe King", 2, 18900), ("202", "Family Suite", 4, 25900))


def _date(value, label):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a valid YYYY-MM-DD date") from exc


class HotelReservation:
    def __init__(self, database="hotel_reservations.sqlite3"):
        self.database = str(database)
        self.initialize()

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.database, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def initialize(self):
        with self.connect() as db:
            db.executescript("""CREATE TABLE IF NOT EXISTS rooms (
                    id INTEGER PRIMARY KEY, room_number TEXT UNIQUE NOT NULL,
                    room_type TEXT NOT NULL, capacity INTEGER NOT NULL CHECK(capacity > 0),
                    nightly_rate_cents INTEGER NOT NULL CHECK(nightly_rate_cents >= 0));
                CREATE TABLE IF NOT EXISTS reservations (
                    id INTEGER PRIMARY KEY, room_id INTEGER NOT NULL REFERENCES rooms(id),
                    check_in TEXT NOT NULL, check_out TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'booked' CHECK(status IN ('booked','checked_in','checked_out','cancelled')),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CHECK(check_in < check_out));""")
            db.executemany("INSERT OR IGNORE INTO rooms (room_number, room_type, capacity, nightly_rate_cents) VALUES (?, ?, ?, ?)", ROOM_SEEDS)

    def rooms(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM rooms ORDER BY room_number")]

    def list_reservations(self, status=None):
        allowed = ("booked", "checked_in", "checked_out", "cancelled")
        if status is not None and status not in allowed:
            raise ValueError(f"Status must be one of: {', '.join(allowed)}")
        query = """SELECT b.id, r.room_number, r.room_type, b.check_in, b.check_out, b.status
                   FROM reservations b JOIN rooms r ON r.id=b.room_id"""
        params = ()
        if status is not None:
            query += " WHERE b.status=?"
            params = (status,)
        query += " ORDER BY b.check_in, b.id"
        with self.connect() as db:
            return [dict(row) for row in db.execute(query, params)]

    def available_rooms(self, check_in, check_out):
        arrival, departure = _date(check_in, "Check-in"), _date(check_out, "Check-out")
        if arrival >= departure:
            raise ValueError("Check-out must be after check-in")
        with self.connect() as db:
            return [dict(row) for row in db.execute("""SELECT r.* FROM rooms r WHERE NOT EXISTS (
                SELECT 1 FROM reservations b WHERE b.room_id=r.id AND b.status IN ('booked','checked_in')
                AND b.check_in < ? AND b.check_out > ?) ORDER BY r.room_number""",
                (departure.isoformat(), arrival.isoformat()))]

    def reserve(self, room_id, check_in, check_out):
        arrival, departure = _date(check_in, "Check-in"), _date(check_out, "Check-out")
        if arrival >= departure:
            raise ValueError("Check-out must be after check-in")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM rooms WHERE id=?", (room_id,)).fetchone() is None:
                raise KeyError(f"No room with ID {room_id}")
            conflict = db.execute("""SELECT 1 FROM reservations WHERE room_id=? AND status IN ('booked','checked_in')
                                  AND check_in < ? AND check_out > ? LIMIT 1""",
                                  (room_id, departure.isoformat(), arrival.isoformat())).fetchone()
            if conflict:
                raise ValueError("Room is already reserved for part of those dates")
            return db.execute("INSERT INTO reservations (room_id, check_in, check_out) VALUES (?, ?, ?)",
                              (room_id, arrival.isoformat(), departure.isoformat())).lastrowid

    def check_in(self, reservation_id, today=None):
        current = _date(today or date.today().isoformat(), "Today")
        with self.connect() as db:
            row = db.execute("SELECT check_in, check_out, status FROM reservations WHERE id=?", (reservation_id,)).fetchone()
            if row is None:
                raise KeyError(f"No reservation with ID {reservation_id}")
            if row["status"] != "booked":
                raise ValueError("Only a booked reservation can check in")
            if not _date(row["check_in"], "Check-in") <= current < _date(row["check_out"], "Check-out"):
                raise ValueError("Check-in is allowed only during the reserved stay")
            db.execute("UPDATE reservations SET status='checked_in' WHERE id=?", (reservation_id,))

    def check_out(self, reservation_id, today=None):
        current = _date(today or date.today().isoformat(), "Today")
        with self.connect() as db:
            row = db.execute("SELECT check_out, status FROM reservations WHERE id=?", (reservation_id,)).fetchone()
            if row is None:
                raise KeyError(f"No reservation with ID {reservation_id}")
            if row["status"] != "checked_in":
                raise ValueError("Only a checked-in reservation can check out")
            if current < _date(row["check_out"], "Check-out"):
                raise ValueError("Check-out date has not arrived yet")
            db.execute("UPDATE reservations SET status='checked_out' WHERE id=?", (reservation_id,))

    def cancel(self, reservation_id):
        with self.connect() as db:
            cursor = db.execute("UPDATE reservations SET status='cancelled' WHERE id=? AND status='booked'", (reservation_id,))
            if not cursor.rowcount:
                raise KeyError(f"No cancellable reservation with ID {reservation_id}")

    def get_reservation(self, reservation_id):
        with self.connect() as db:
            row = db.execute("""SELECT b.id, r.room_number, r.room_type, b.check_in, b.check_out, b.status
                             FROM reservations b JOIN rooms r ON r.id=b.room_id WHERE b.id=?""", (reservation_id,)).fetchone()
            if row is None:
                raise KeyError(f"No reservation with ID {reservation_id}")
            return dict(row)


def _show_rooms(rows):
    if not rows:
        print("No rooms available for those dates.")
    for room in rows:
        print(f"#{room['id']} Room {room['room_number']} — {room['room_type']}, up to {room['capacity']} guests, ${room['nightly_rate_cents'] / 100:.2f}/night (display only)")


def main():
    hotel = HotelReservation()
    while True:
        print("\nHotel Reservations | 1 Show rooms  2 List reservations  3 Check availability  4 Reserve  5 Check in  6 Check out  7 Cancel  0 Exit")
        choice = input("> ").strip()
        try:
            if choice == "0":
                break
            if choice == "1":
                _show_rooms(hotel.rooms())
            elif choice == "2":
                reservations = hotel.list_reservations()
                if not reservations:
                    print("No reservations yet.")
                for reservation in reservations:
                    print(f"#{reservation['id']} Room {reservation['room_number']} — {reservation['check_in']} to {reservation['check_out']} | {reservation['status']}")
            elif choice in ("3", "4"):
                arrival = input("Check-in date YYYY-MM-DD: ").strip()
                departure = input("Check-out date YYYY-MM-DD: ").strip()
                rooms = hotel.available_rooms(arrival, departure)
                _show_rooms(rooms)
                if choice == "4" and rooms:
                    room_id = int(input("Room ID to reserve: "))
                    reservation_id = hotel.reserve(room_id, arrival, departure)
                    print(f"Reservation confirmed: #{reservation_id}. Keep this ID to check in, check out, or cancel. No guest details are collected.")
            elif choice == "4":
                reservation_id = int(input("Reservation ID: "))
                hotel.check_in(reservation_id)
                print("Checked in.")
            elif choice == "5":
                reservation_id = int(input("Reservation ID: "))
                hotel.check_out(reservation_id)
                print("Checked out.")
            elif choice == "7":
                hotel.cancel(int(input("Reservation ID: ")))
                print("Reservation cancelled.")
            else:
                print("Choose one of the listed options.")
        except (ValueError, KeyError) as exc:
            print(f"Could not complete request: {exc}")


if __name__ == "__main__":
    main()
