"""RSS discovery and HTML discovery share a polite, robots-aware HTTP client."""
import logging
import time
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import feedparser
import requests
from bs4 import BeautifulSoup

from .cleaning import canonical_url


class NewsHTTP:
    def __init__(self, config):
        self.timeout = config.get('request_timeout', 20)
        self.delay = config.get('request_delay', 1)
        self.agent = config.get('user_agent', 'NewsLearningProject/1.0')
        self.session = requests.Session()
        self.session.headers['User-Agent'] = self.agent
        self.robots = {}
        self.last_request = {}

    def close(self):
        self.session.close()

    def _request(self, url, delay=None):
        host = urlsplit(url).netloc
        pause = max(self.delay, delay or 0) - (time.monotonic() - self.last_request.get(host, 0))
        if pause > 0:
            time.sleep(pause)
        try:
            response = self.session.get(url, timeout=self.timeout, allow_redirects=False)
        except requests.RequestException as exc:
            raise ValueError(f'뉴스 HTTP 요청 실패 ({type(exc).__name__})') from None
        finally:
            self.last_request[host] = time.monotonic()
        if response.encoding == 'ISO-8859-1':
            response.encoding = response.apparent_encoding
        return response

    def policy(self, url):
        parts = urlsplit(url)
        origin = f'{parts.scheme}://{parts.netloc}'
        if origin not in self.robots:
            response = self._request(origin + '/robots.txt')
            parser = RobotFileParser()
            if response.status_code == 404:
                parser.parse(['User-agent: *', 'Allow: /'])
            elif response.status_code == 200:
                parser.parse(response.text.splitlines())
            else:
                raise ValueError(f'robots.txt 확인 실패: HTTP {response.status_code}')
            self.robots[origin] = parser
        return self.robots[origin]

    def get(self, url):
        for _ in range(6):
            canonical_url(url)  # Reject non-HTTP URLs and embedded credentials.
            policy = self.policy(url)
            if not policy.can_fetch(self.agent, url):
                raise ValueError('robots.txt에 의해 수집이 금지된 URL입니다.')
            delay = policy.crawl_delay(self.agent) or 0
            rate = policy.request_rate(self.agent)
            if rate and rate.requests:
                delay = max(delay, rate.seconds / rate.requests)
            response = self._request(url, delay)
            if response.status_code in (301, 302, 303, 307, 308):
                if not response.headers.get('Location'):
                    raise ValueError('Location 없는 리다이렉트')
                url = urljoin(url, response.headers['Location'])
                continue
            if response.status_code != 200:
                raise ValueError(f'뉴스 HTTP 오류: {response.status_code}')
            return response
        raise ValueError('뉴스 리다이렉트 횟수 초과')


def parse_article(html, url, source):
    soup = BeautifulSoup(html, 'html.parser')
    title_node = soup.select_one('h1')
    container = soup.select_one(source.get('body_selector', 'article'))
    if container is None:
        raise ValueError('본문 CSS 선택자와 일치하는 요소가 없습니다.')
    for node in container.select('script, style, nav, aside, figure, .wp-block-buttons'):
        node.decompose()
    paragraphs = container.select('p')
    body = '\n'.join(p.get_text(' ', strip=True) for p in paragraphs) if paragraphs else container.get_text(' ', strip=True)
    date_node = soup.select_one('meta[property="article:published_time"], meta[name="parsely-pub-date"], meta[name="date"], time[datetime]')
    category_node = soup.select_one('meta[property="article:section"]')
    return {
        'url': url,
        'title': title_node.get_text(' ', strip=True) if title_node else '',
        'body': body,
        'published_at': (date_node.get('content') or date_node.get('datetime')) if date_node else '',
        'category': category_node.get('content') if category_node else source.get('category', '미분류'),
    }


def fetch(store, config, source_name, method, limit):
    sources = config.get('sources', {})
    if source_name not in sources:
        raise ValueError(f'등록되지 않은 뉴스 소스: {source_name}')
    source = sources[source_name]
    client = NewsHTTP(config)
    counts = {'success': 0, 'failed': 0}
    try:
        if method == 'rss':
            response = client.get(source['rss_url'])
            feed = feedparser.parse(response.content)
            if not feed.entries:
                raise ValueError('RSS 항목이 없습니다. 피드 URL과 형식을 확인하세요.')
            entries = [(entry.get('link', ''), entry) for entry in feed.entries[:limit]]
        else:
            response = client.get(source['crawl_url'])
            soup = BeautifulSoup(response.text, 'html.parser')
            entries, seen = [], set()
            for link in soup.select(source.get('link_selector', 'article a[href]')):
                url = urljoin(response.url, link.get('href', ''))
                # A source config never silently widens crawling to another host.
                if urlsplit(url).netloc != urlsplit(response.url).netloc:
                    continue
                try:
                    key = canonical_url(url)
                except ValueError:
                    continue
                if key not in seen:
                    seen.add(key)
                    entries.append((url, {}))
                if len(entries) >= limit:
                    break
            if not entries:
                raise ValueError('기사 링크가 없습니다. link_selector를 확인하세요.')
        for url, entry in entries:
            try:
                response = client.get(url)
                article = parse_article(response.text, response.url, source)
                if method == 'rss':
                    article['title'] = entry.get('title') or article['title']
                    article['published_at'] = entry.get('published') or entry.get('updated') or article['published_at']
                    tags = entry.get('tags', [])
                    if tags:
                        article['category'] = tags[0].get('term') or article['category']
                article['original_html'] = response.text
                if entry:
                    article['original_feed_entry'] = dict(entry)
                store.add_raw(source_name, method, article)
                counts['success'] += 1
            except (ValueError, KeyError) as exc:
                counts['failed'] += 1
                logging.warning('기사 수집 스킵: %s', exc)
        logging.info('수집 완료 source=%s method=%s: %s', source_name, method, counts)
        return counts
    finally:
        client.close()
