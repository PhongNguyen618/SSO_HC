import datetime

ts = 1781542800
dt = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc)
print(f"Timestamp {ts} in UTC: {dt}")

dt_vn = datetime.datetime.fromtimestamp(ts, datetime.timezone(datetime.timedelta(hours=7)))
print(f"Timestamp {ts} in GMT+7: {dt_vn}")

# Calculate actual timestamp for 2026-06-16 00:00:00 GMT+7
dt_target = datetime.datetime(2026, 6, 16, 0, 0, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=7)))
print(f"Actual 2026-06-16 00:00:00 GMT+7 timestamp: {int(dt_target.timestamp())}")
