import sqlite3, pathlib
schema = pathlib.Path('schema.sql').read_text(encoding='utf-8')
con = sqlite3.connect('tracker.db')
con.executescript(schema)
cur = con.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print('Tables created:', tables)
cur2 = con.execute("PRAGMA table_info(issues)")
print('issues columns:', [r[1] for r in cur2.fetchall()])
cur3 = con.execute("PRAGMA table_info(raw_reports)")
print('raw_reports columns:', [r[1] for r in cur3.fetchall()])
con.close()
print('DB file size:', pathlib.Path('tracker.db').stat().st_size, 'bytes')
