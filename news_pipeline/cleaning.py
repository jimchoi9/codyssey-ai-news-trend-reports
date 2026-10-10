"""Normalize validated raw records once; retain rejected records for auditing."""
import html
import json
import logging
import re
import unicodedata
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup
from .storage import now


def text(value):
    soup = BeautifulSoup(str(value or ''), 'html.parser')
    for node in soup(['script', 'style']):
        node.decompose()
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', html.unescape(soup.get_text(' ', strip=True)))).strip()


def canonical_url(value):
    parts = urlsplit(str(value or '').strip())
    if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password:
        raise ValueError('유효한 HTTP(S) URL이 필요합니다.')
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith('utm_') and k.lower() not in ('fbclid', 'gclid')]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or '/', urlencode(sorted(query)), ''))


def date_time(value):
    if not value:
        raise ValueError('발행일 누락')
    try:
        dt = datetime.fromisoformat(str(value).strip().replace('Z', '+00:00'))
    except ValueError:
        try:
            dt = parsedate_to_datetime(str(value))
        except (ValueError, TypeError) as exc:
            raise ValueError('발행일 형식 오류') from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec='seconds')


def clean(store, policy='skip', limit=None):
    counts = dict(inserted=0, updated=0, duplicate=0, invalid=0)
    for raw in store.pending()[:limit]:
        try:
            item = json.loads(raw['payload'])
            title, body = text(item.get('title')), text(item.get('body'))
            if not title or not body:
                raise ValueError('제목 또는 본문 누락')
            url = canonical_url(item.get('url'))
            published = date_time(item.get('published_at'))
            category = text(item.get('category')) or '미분류'
            with store.db:
                old = store.db.execute('SELECT * FROM clean_news WHERE url=?', (url,)).fetchone()
                if old and policy == 'skip':
                    status = 'duplicate'
                elif old:
                    changed = any(old[k] != v for k, v in [('title', title), ('body', body), ('category', category), ('published_at', published)])
                    store.db.execute('''UPDATE clean_news SET title=?,body=?,category=?,published_at=?,raw_id=?,updated_at=?,
                        summary=?,summarized_at=?,summary_model=? WHERE id=?''',
                        (title, body, category, published, raw['id'], now(),
                         None if changed else old['summary'], None if changed else old['summarized_at'],
                         None if changed else old['summary_model'], old['id']))
                    status = 'updated'
                else:
                    store.db.execute('''INSERT INTO clean_news(url,title,body,category,published_at,collected_at,source,raw_id,updated_at)
                        VALUES(?,?,?,?,?,?,?,?,?)''', (url, title, body, category, published, raw['collected_at'], raw['source'], raw['id'], now()))
                    status = 'inserted'
                store.db.execute('UPDATE raw_news SET clean_status=?,error=NULL WHERE id=?', (status, raw['id']))
            counts[status] += 1
        except (ValueError, TypeError, AttributeError) as exc:
            with store.db:
                store.db.execute("UPDATE raw_news SET clean_status='invalid',error=? WHERE id=?", (str(exc), raw['id']))
            counts['invalid'] += 1
            logging.warning('정제 스킵 raw_id=%s: %s', raw['id'], exc)
    logging.info('정제 완료: %s', counts)
    return counts
