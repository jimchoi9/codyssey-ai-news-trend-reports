"""Persistent raw events, current clean articles, and immutable analysis snapshots."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
        PRAGMA foreign_keys = ON;
        CREATE TABLE IF NOT EXISTS raw_news (
            id INTEGER PRIMARY KEY, source TEXT NOT NULL, method TEXT NOT NULL,
            collected_at TEXT NOT NULL, payload TEXT NOT NULL,
            clean_status TEXT NOT NULL DEFAULT 'pending', error TEXT);
        CREATE TABLE IF NOT EXISTS clean_news (
            id INTEGER PRIMARY KEY, url TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
            body TEXT NOT NULL, category TEXT NOT NULL, published_at TEXT NOT NULL,
            collected_at TEXT NOT NULL, source TEXT NOT NULL, raw_id INTEGER NOT NULL REFERENCES raw_news(id),
            summary TEXT, summarized_at TEXT, summary_model TEXT, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, filters TEXT NOT NULL,
            article_ids TEXT NOT NULL, snapshot TEXT NOT NULL, result TEXT NOT NULL, model TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS clean_filters ON clean_news(published_at, category);
        ''')

    def close(self):
        self.db.close()

    def add_raw(self, source, method, payload):
        with self.db:
            cursor = self.db.execute('INSERT INTO raw_news(source,method,collected_at,payload) VALUES(?,?,?,?)',
                                     (source, method, now(), json.dumps(payload, ensure_ascii=False)))
        return cursor.lastrowid

    def pending(self):
        return [dict(r) for r in self.db.execute("SELECT * FROM raw_news WHERE clean_status='pending' ORDER BY id")]

    def articles(self, filters=None, status=None, article_id=None, limit=None):
        filters = filters or {}
        terms, values = [], []
        for key, operator, field in [('date_from', '>=', 'substr(published_at,1,10)'), ('date_to', '<=', 'substr(published_at,1,10)'), ('category', '=', 'category')]:
            if filters.get(key):
                terms.append(f'{field} {operator} ?')
                values.append(filters[key])
        if status:
            terms.append('summary IS ' + ('NOT NULL' if status == 'summarized' else 'NULL'))
        if article_id is not None:
            terms.append('id = ?')
            values.append(article_id)
        sql = 'SELECT * FROM clean_news' + (' WHERE ' + ' AND '.join(terms) if terms else '') + ' ORDER BY published_at DESC, id'
        if limit:
            sql += ' LIMIT ?'
            values.append(limit)
        return [dict(r) for r in self.db.execute(sql, values)]

    def save_summary(self, article_id, summary, model):
        with self.db:
            self.db.execute('UPDATE clean_news SET summary=?, summarized_at=?, summary_model=? WHERE id=?',
                            (summary, now(), model, article_id))

    def save_analysis(self, filters, articles, result, model):
        with self.db:
            cursor = self.db.execute('INSERT INTO analyses(created_at,filters,article_ids,snapshot,result,model) VALUES(?,?,?,?,?,?)',
                (now(), json.dumps(filters, sort_keys=True), json.dumps([r['id'] for r in articles]),
                 json.dumps(articles, ensure_ascii=False), json.dumps(result, ensure_ascii=False), model))
        return cursor.lastrowid

    def latest_analysis(self, filters):
        row = self.db.execute('SELECT * FROM analyses WHERE filters=? ORDER BY id DESC LIMIT 1',
                              (json.dumps(filters, sort_keys=True),)).fetchone()
        return dict(row) if row else None
