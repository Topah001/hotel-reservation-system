import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from app import HotelReservation


class HotelReservationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.hotel = HotelReservation(Path(self.temp.name) / "test.sqlite3")
        self.room = self.hotel.rooms()[0]
        self.arrival = (date.today() + timedelta(days=2)).isoformat()
        self.departure = (date.today() + timedelta(days=5)).isoformat()

    def tearDown(self):
        self.temp.cleanup()

    def test_seeded_rooms_and_available_list(self):
        self.assertGreaterEqual(len(self.hotel.rooms()), 4)
        self.assertIn(self.room, self.hotel.available_rooms(self.arrival, self.departure))

    def test_reservation_and_overlap(self):
        reservation_id = self.hotel.reserve(self.room["id"], self.arrival, self.departure)
        self.assertEqual(self.hotel.get_reservation(reservation_id)["status"], "booked")
        self.assertEqual(self.hotel.list_reservations()[0]["id"], reservation_id)
        self.assertEqual(self.hotel.list_reservations(status="booked")[0]["room_number"], self.room["room_number"])
        self.assertNotIn(self.room, self.hotel.available_rooms(self.arrival, self.departure))
        with self.assertRaisesRegex(ValueError, "already reserved"):
            self.hotel.reserve(self.room["id"], self.arrival, self.departure)

    def test_adjacent_stays_do_not_overlap(self):
        self.hotel.reserve(self.room["id"], self.arrival, self.departure)
        next_arrival = self.departure
        next_departure = (date.fromisoformat(next_arrival) + timedelta(days=2)).isoformat()
        self.hotel.reserve(self.room["id"], next_arrival, next_departure)

    def test_different_rooms_do_not_conflict(self):
        other = self.hotel.rooms()[1]
        self.hotel.reserve(self.room["id"], self.arrival, self.departure)
        self.hotel.reserve(other["id"], self.arrival, self.departure)

    def test_cancel_releases_room(self):
        reservation_id = self.hotel.reserve(self.room["id"], self.arrival, self.departure)
        self.hotel.cancel(reservation_id)
        self.assertEqual(self.hotel.get_reservation(reservation_id)["status"], "cancelled")
        self.assertIn(self.room, self.hotel.available_rooms(self.arrival, self.departure))
        with self.assertRaises(KeyError):
            self.hotel.cancel(reservation_id)

    def test_check_in_and_out_lifecycle(self):
        reservation_id = self.hotel.reserve(self.room["id"], self.arrival, self.departure)
        with self.assertRaisesRegex(ValueError, "during the reserved stay"):
            self.hotel.check_in(reservation_id, today=date.today().isoformat())
        self.hotel.check_in(reservation_id, today=self.arrival)
        self.assertEqual(self.hotel.get_reservation(reservation_id)["status"], "checked_in")
        with self.assertRaisesRegex(ValueError, "has not arrived"):
            self.hotel.check_out(reservation_id, today=self.arrival)
        self.hotel.check_out(reservation_id, today=self.departure)
        self.assertEqual(self.hotel.get_reservation(reservation_id)["status"], "checked_out")

    def test_validates_dates_and_room_ids(self):
        for start, end in (("bad", self.departure), (self.arrival, self.arrival), (self.departure, self.arrival)):
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                self.hotel.reserve(self.room["id"], start, end)
        with self.assertRaises(KeyError):
            self.hotel.reserve(999, self.arrival, self.departure)

    def test_no_guest_private_data_is_stored(self):
        with self.hotel.connect() as db:
            columns = {row[1] for row in db.execute("PRAGMA table_info(reservations)")}
        self.assertFalse(columns & {"guest_name", "email", "phone", "payment_card"})


if __name__ == "__main__":
    unittest.main()
