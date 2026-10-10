"""Portable exports. Neutralize spreadsheet formulas in untrusted news text."""
import csv
import re
from pathlib import Path

FIELDS = ['id', 'title', 'url', 'category', 'published_at', 'collected_at', 'source', 'body', 'summary']


def safe_cell(value):
    if not isinstance(value, str):
        return value
    value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', value)
    if value.lstrip().startswith(('=', '+', '-', '@')):
        return "'" + value
    return value


def export(store, config, filters, format, status=None):
    articles = store.articles(filters, status=status)
    output = Path(config['output_dir'])
    output.mkdir(parents=True, exist_ok=True)
    path = output / ('news.csv' if format == 'csv' else 'news.xlsx')
    if format == 'csv':
        with path.open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(FIELDS)
            writer.writerows([safe_cell(a[k]) for k in FIELDS] for a in articles)
    else:
        from openpyxl import Workbook
        # Excel cells cannot store more than 32767 characters. Fail rather than silently lose text.
        if any(isinstance(a[k], str) and len(safe_cell(a[k])) > 32767 for a in articles for k in FIELDS):
            raise ValueError('Excel 셀 길이 제한(32767자)을 초과했습니다. CSV를 사용하세요.')
        book = Workbook()
        sheet = book.active
        sheet.title = '뉴스'
        sheet.append(FIELDS)
        for article in articles:
            sheet.append([safe_cell(article[k]) for k in FIELDS])
        sheet.freeze_panes = 'A2'
        sheet.auto_filter.ref = sheet.dimensions
        for column in ('B', 'C', 'H', 'I'):
            sheet.column_dimensions[column].width = 45
        book.save(path)
        book.close()
    return path, len(articles)
