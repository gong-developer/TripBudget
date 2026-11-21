"""Small persistent stores shared by workers on the same local volume."""
from collections.abc import MutableMapping
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sqlite3
import time

ROOT = Path(__file__).resolve().parents[2]


@contextmanager
def database(env_name, filename):
    path = data_path(env_name, filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=5)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def data_path(env_name, filename):
    return Path(os.getenv(env_name) or Path(os.getenv('APP_DATA_DIR') or ROOT / '.tools') / filename)


class DestinationStore(MutableMapping):
    @contextmanager
    def connection(self):
        with database('DESTINATION_DB', 'destinations.sqlite3') as db:
            db.execute('CREATE TABLE IF NOT EXISTS destinations (name TEXT PRIMARY KEY, data TEXT NOT NULL, touched REAL NOT NULL)')
            yield db

    def __getitem__(self, name):
        with self.connection() as db:
            row = db.execute('SELECT data FROM destinations WHERE name=?', (name,)).fetchone()
        if row is None:
            raise KeyError(name)
        return json.loads(row[0])

    def __setitem__(self, name, city):
        with self.connection() as db:
            db.execute('INSERT OR REPLACE INTO destinations VALUES (?, ?, ?)',
                       (name, json.dumps(city, ensure_ascii=False), time.time()))
            db.execute('DELETE FROM destinations WHERE name IN (SELECT name FROM destinations ORDER BY touched DESC LIMIT -1 OFFSET 1000)')

    def __delitem__(self, name):
        with self.connection() as db:
            if not db.execute('DELETE FROM destinations WHERE name=?', (name,)).rowcount:
                raise KeyError(name)

    def __iter__(self):
        with self.connection() as db:
            names = [row[0] for row in db.execute('SELECT name FROM destinations ORDER BY touched')]
        return iter(names)

    def __len__(self):
        with self.connection() as db:
            return db.execute('SELECT count(*) FROM destinations').fetchone()[0]

    def values(self):
        with self.connection() as db:
            return [json.loads(row[0]) for row in db.execute('SELECT data FROM destinations ORDER BY touched')]

    def move_to_end(self, name):
        with self.connection() as db:
            db.execute('UPDATE destinations SET touched=? WHERE name=?', (time.time(), name))

    def popitem(self, last=True):
        with self.connection() as db:
            row = db.execute('SELECT name,data FROM destinations ORDER BY touched ' + ('DESC' if last else 'ASC') + ' LIMIT 1').fetchone()
            if row is None:
                raise KeyError('empty destination store')
            db.execute('DELETE FROM destinations WHERE name=?', (row[0],))
        return row[0], json.loads(row[1])

    def clear(self):
        with self.connection() as db:
            db.execute('DELETE FROM destinations')
