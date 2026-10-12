"""Small donation-feed and polling helpers for CircuitPython and desktop tests."""

PAGE_SIZE = 10
MAX_PENDING = 12
MAX_SEEN = 128
OVERLAP_SECONDS = 120
MAX_NAME = 48


def api_server(server):
    """Route legacy Extra Life configuration to the current DonorDrive host."""
    server = server.rstrip("/")
    if server in ("https://www.extra-life.org", "https://extra-life.org"):
        return "https://dd.extra-life.org"
    return server


def _created_time(value):
    """Parse a UTC API timestamp into integer microseconds, preserving ties."""
    if not isinstance(value, str):
        raise ValueError("Donation timestamp must be a UTC string")
    if value.endswith("Z"):
        value = value[:-1]
    elif value.endswith("+0000"):
        value = value[:-5]
    elif value.endswith("+00:00"):
        value = value[:-6]
    else:
        raise ValueError("Donation timestamp must be UTC")
    try:
        date, clock = value.split("T")
        year, month, day = [int(part) for part in date.split("-")]
        hour, minute, seconds = clock.split(":")
        second, _, fraction = seconds.partition(".")
        hour, minute, second = int(hour), int(minute), int(second)
        if fraction and (not fraction.isdigit() or len(fraction) > 6):
            raise ValueError("Invalid timestamp precision")
        leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
        months = (31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
        if not (1970 <= year <= 2099 and 1 <= month <= 12):
            raise ValueError("Invalid date")
        if not (1 <= day <= months[month - 1]):
            raise ValueError("Invalid day")
        if not (0 <= hour < 24 and 0 <= minute < 60 and 0 <= second < 60):
            raise ValueError("Invalid time")
        prior = year - 1
        days = 365 * prior + prior // 4 - prior // 100 + prior // 400
        # Days before 1970-01-01 in the Gregorian calendar.
        days += sum(months[: month - 1]) + day - 1 - 719162
        return ((days * 24 + hour) * 3600 + minute * 60 + second) * 1000000 + int(
            (fraction + "000000")[:6]
        )
    except (TypeError, IndexError) as error:
        raise ValueError("Invalid donation timestamp") from error


def _date_text(timestamp):
    """Format a cursor in UTC without the CPython-only time.gmtime function."""
    days, seconds = divmod(timestamp // 1000000, 86400)
    if days < 0:
        raise ValueError("Invalid cursor date")
    for year in range(1970, 2100):
        leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
        year_days = 366 if leap else 365
        if days < year_days:
            break
        days -= year_days
    else:
        raise ValueError("Invalid cursor date")
    months = (31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    month = 1
    for month_days in months:
        if days < month_days:
            break
        days -= month_days
        month += 1
    hour, seconds = divmod(seconds, 3600)
    minute, second = divmod(seconds, 60)
    fraction = "{:06d}".format(timestamp % 1000000).rstrip("0") or "000"
    return "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}.{}+0000".format(
        year, month, days + 1, hour, minute, second, fraction
    )


def _encode(value):
    """Encode our ASCII query fields without a device urllib dependency."""
    return "".join(
        (
            character
            if (
                "A" <= character <= "Z"
                or "a" <= character <= "z"
                or "0" <= character <= "9"
                or character in "-_."
            )
            else "%{:02X}".format(ord(character))
        )
        for character in str(value)
    )


class Donation:
    def __init__(self, donation_id, created, name, amount_text):
        self.donation_id = donation_id
        self.created = created
        self.name = name
        self.amount_text = amount_text

    @property
    def key(self):
        return self.created, self.donation_id


def normalize_donation(record):
    """Keep only public display fields, with bounded ASCII names."""
    if not isinstance(record, dict):
        raise ValueError("Donation must be an object")
    identifier = record.get("donationID")
    if (
        not isinstance(identifier, str)
        or not 1 <= len(identifier) <= 64
        or not all(
            "A" <= c <= "Z" or "a" <= c <= "z" or "0" <= c <= "9" or c in "-_"
            for c in identifier
        )
    ):
        raise ValueError("Invalid donation ID")
    created = _created_time(record.get("createdDateUTC"))
    raw_name = record.get("displayName")
    name = "ANON"
    if isinstance(raw_name, str):
        name = " ".join(raw_name[:256].split()).upper()
        name = "".join(c if 32 <= ord(c) < 127 else "?" for c in name) or "ANON"
        if len(name) > MAX_NAME:
            name = name[: MAX_NAME - 3] + "..."
    amount = record.get("amount")
    amount_text = "THANKS!"
    if (
        not isinstance(amount, bool)
        and isinstance(amount, (int, float))
        and 0 <= amount <= 1000000000
    ):
        cents = int(amount * 100 + 0.5)
        amount_text = "${:,}".format(cents // 100)
        if cents % 100:
            amount_text += ".{:02d}".format(cents % 100)
    return Donation(identifier, created, name, amount_text)


class DonationTracker:
    """Bounded pending gifts, keyset paging, and a recent-ID overlap window."""

    def __init__(self, max_pending=MAX_PENDING, page_size=PAGE_SIZE, max_seen=MAX_SEEN):
        self.max_pending = max_pending
        self.page_size = page_size
        self.max_seen = max_seen
        self.initialized = False
        self.baseline = None
        self.watermark = None
        self.cursor = None
        self.retired = None
        self.pending = []
        self.seen = {}

    @property
    def has_room(self):
        return len(self.pending) < self.max_pending

    def pop(self):
        return self.pending.pop(0) if self.pending else None

    def _remember(self, donation):
        self.watermark = max(self.watermark or donation.created, donation.created)
        self.seen[donation.donation_id] = donation.key
        cutoff = self.watermark - OVERLAP_SECONDS * 1000000
        expired = [
            identifier for identifier, key in self.seen.items() if key[0] < cutoff
        ]
        for identifier in expired:
            key = self.seen.pop(identifier)
            self.retired = max(self.retired or key, key)
        while len(self.seen) > self.max_seen:
            identifier = min(self.seen, key=lambda identifier: self.seen[identifier])
            key = self.seen.pop(identifier)
            self.retired = max(self.retired or key, key)

    def accept_page(self, records):
        """Isolate invalid gifts, validate ordering, and stop before unqueued gifts."""
        if not isinstance(records, list):
            raise ValueError("Donation feed must be an array")
        donations = []
        valid_records = []
        for record in records:
            try:
                donation = normalize_donation(record)
            except ValueError:
                # A bad initial baseline must retry rather than replay history.
                if not self.initialized:
                    raise
                print("Excluding donation with invalid ID or timestamp")
                continue
            donations.append(donation)
            valid_records.append(record)
        if records and not donations:
            raise ValueError("Donation page has no usable IDs/timestamps")
        if not self.initialized:
            self.baseline = max((d.created for d in donations), default=None)
            self.watermark = self.baseline
            self.initialized = True
            return
        if any(a.key > b.key for a, b in zip(donations, donations[1:])):
            raise ValueError("Donation feed was not ordered ascending")
        for donation, record in zip(donations, valid_records):
            old = (
                (self.baseline is not None and donation.created <= self.baseline)
                or (self.retired is not None and donation.key <= self.retired)
                or donation.donation_id in self.seen
            )
            if not old and not record.get("isRegFee", False):
                if not self.has_room:
                    return
                if (
                    record.get("amount") is not None
                    and donation.amount_text == "THANKS!"
                ):
                    print("Donation has invalid amount; displaying THANKS!")
                self.pending.append(donation)
            if not old:
                self._remember(donation)
            self.cursor = donation.key
        if len(records) < self.page_size:
            self.cursor = None

    def url(self, server, participant_id):
        """Use a stable ascending keyset, including bounded overlap on new scans."""
        base = "{}/api/participants/{}/donations".format(
            api_server(server), participant_id
        )
        if not self.initialized:
            return base + "?version=1.3&limit=1&orderBy=createdDateUTC%20DESC"
        query = [("version", "1.3"), ("limit", self.page_size)]
        query.append(("orderBy", "createdDateUTC ASC,donationID ASC"))
        conditions = []
        if self.watermark is not None:
            lower = max(self.baseline or 0, self.watermark - OVERLAP_SECONDS * 1000000)
            conditions.append("createdDateUTC >= '{}'".format(_date_text(lower)))
        key = self.cursor or self.retired
        if key is not None:
            date = _date_text(key[0])
            conditions.append(
                "(createdDateUTC > '{0}' OR (createdDateUTC = '{0}' "
                "AND donationID > '{1}'))".format(date, key[1])
            )
        if conditions:
            query.append(("where", " AND ".join(conditions)))
        return base + "?" + "&".join(_encode(k) + "=" + _encode(v) for k, v in query)


class PollSchedule:
    """Independent deadlines, bounded retries, and a shared API cooldown."""

    def __init__(self, refresh_frequency):
        self.interval = max(30, refresh_frequency)
        self.next_due = {"sync": 0, "total": 0, "donations": 0}
        self.failures = {"sync": 0, "total": 0, "donations": 0}
        self.api_ready_at = 0

    def ready(self, now, busy=False, feed_has_room=True):
        if busy:
            return None
        if now >= self.next_due["sync"]:
            return "sync"
        if now < self.api_ready_at:
            return None
        jobs = ("total", "donations") if feed_has_room else ("total",)
        job = min(jobs, key=lambda candidate: self.next_due[candidate])
        return job if now >= self.next_due[job] else None

    def record(self, job, now, success):
        if success:
            self.failures[job] = 0
            delay = 1800 if job == "sync" else self.interval
        else:
            self.failures[job] = min(5, self.failures[job] + 1)
            delay = min(
                300, (60 if job == "sync" else 30) * 2 ** (self.failures[job] - 1)
            )
        self.next_due[job] = now + delay
        if job != "sync":
            self.api_ready_at = now + 15


def fetch_json(network, url, empty_list=False):
    """Always release the response, including HTTP and JSON failures."""
    response = network.fetch(url)
    try:
        if empty_list and response.status_code == 204:
            return []
        if response.status_code != 200:
            raise RuntimeError("HTTP {}".format(response.status_code))
        return response.json()
    finally:
        response.close()
