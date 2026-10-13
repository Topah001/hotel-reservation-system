# Hotel Reservation System

A local hotel room availability and reservation CLI built with Python 3.13, SQLite, and the standard library. View sample rooms and reservations, check room availability for a date range, reserve a room, cancel a booking, and record check-in/check-out. Date ranges use hotel convention `[check-in, check-out)`: the checkout date is not an occupied night, so consecutive stays can touch on the same date.

The sample room inventory is fictional and rates are display-only. **There are no payments.** This demo does not collect guest names, contact information, or payment details; reservation IDs are sufficient to manage local bookings. It is not connected to a real hotel.

## Run

```powershell
py -3.13 app.py
```

If the Python launcher is unavailable, run with your Python 3.13 executable, for example:

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" app.py
```

The first run creates `hotel_reservations.sqlite3` and seeds four sample rooms. Use ISO dates (`YYYY-MM-DD`) and keep the reservation ID shown after booking. Database files are local and excluded from Git.

## Tests

```powershell
py -3.13 -m unittest -v
```

No external packages or network connection are needed.
