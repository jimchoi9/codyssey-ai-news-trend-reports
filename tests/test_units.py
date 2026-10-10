import json

from news_pipeline.collectors import parse_article


def test_nasa_published_date_uses_parsely_metadata():
    html = '''<html><head><meta name="parsely-pub-date" content="2026-10-02T15:49:26Z"></head>
    <body><h1>NASA 뉴스</h1><div class="entry-content"><p>기사 본문</p></div></body></html>'''
    article = parse_article(html, 'https://www.nasa.gov/news-release/test/', {'body_selector': '.entry-content'})
    assert article['published_at'] == '2026-10-02T15:49:26Z'


def test_default_crawl_selector_excludes_navigation():
    from bs4 import BeautifulSoup
    from pathlib import Path
    config = json.loads((Path(__file__).resolve().parents[1] / 'config.json').read_text())
    page = BeautifulSoup('''<nav><a href="https://www.nasa.gov/missions/">메뉴</a></nav>
    <main><div class="hds-content-item"><a href="https://www.nasa.gov/news-release/news/">기사</a>
    <a href="https://www.nasa.gov/directorates/challenge/">공모 페이지</a></div></main>''', 'html.parser')
    urls = [n['href'] for n in page.select(config['sources']['nasa']['link_selector'])]
    assert urls == ['https://www.nasa.gov/news-release/news/']


def test_clean_rejections_and_duplicate_metrics(tmp_path):
    from news_pipeline.storage import Store
    from news_pipeline.cleaning import clean
    from news_pipeline.reporting import metrics
    store = Store(tmp_path / 'db.sqlite')
    valid = {'title': ' 정상  제목 ', 'body': '<p>본문</p>', 'url': 'https://example.com/a?utm_source=x', 'published_at': '2026-10-07', 'category': ''}
    for item in [valid, {**valid, 'url': 'https://example.com/a'}, {**valid, 'body': ''}, {**valid, 'published_at': 'not-a-date'}]:
        store.add_raw('test', 'rss', item)
    result = clean(store)
    assert result == {'inserted': 1, 'updated': 0, 'duplicate': 1, 'invalid': 2}
    article = store.articles()[0]
    assert article['title'] == '정상 제목' and article['category'] == '미분류'
    quality = metrics(store, store.articles())
    assert quality['invalid_rate'] == 0.5 and quality['duplicate_rate'] == 0.25
    clean(store)
    assert metrics(store, store.articles()) == quality
    store.close()


def test_spreadsheet_formula_is_exported_as_text(tmp_path):
    from news_pipeline.storage import Store
    from news_pipeline.cleaning import clean
    from news_pipeline.exporting import export
    from openpyxl import load_workbook
    store = Store(tmp_path / 'db.sqlite')
    store.add_raw('test', 'rss', {'title': '=1+1', 'body': '@SUM(A1)', 'url': 'https://example.com/a', 'published_at': '2026-10-07'})
    clean(store)
    path, _ = export(store, {'output_dir': str(tmp_path)}, {}, 'excel')
    book = load_workbook(path)
    assert book.active['B2'].data_type == 's'
    assert book.active['B2'].value == "'=1+1"
    book.close()
    store.close()


def test_ai_timeout_is_safe_and_missing_key_is_actionable(monkeypatch):
    import pytest
    import requests
    from news_pipeline.ai import AIClient
    with pytest.raises(ValueError, match='OPENAI_API_KEY'):
        AIClient({'ai': {}})
    client = AIClient({'ai': {'api_key': 'must-not-leak', 'model': 'test'}})

    def timeout(*args, **kwargs):
        raise requests.Timeout('must-not-leak')

    monkeypatch.setattr(requests, 'post', timeout)
    with pytest.raises(ValueError) as error:
        client.complete('요약', {'body': '본문'})
    assert 'Timeout' in str(error.value)
    assert 'must-not-leak' not in str(error.value)
