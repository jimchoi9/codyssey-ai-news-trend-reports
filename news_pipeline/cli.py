"""Six required argparse subcommands; all errors have nonzero exit status."""
import argparse
import json
import logging
import sqlite3
from datetime import date
from pathlib import Path

from .config import configure_logging, load_config
from .storage import Store


def positive(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError('양의 정수를 입력하세요.')
    return number


def iso_date(value):
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise argparse.ArgumentTypeError('날짜는 YYYY-MM-DD 형식이어야 합니다.') from None


def parser():
    root = argparse.ArgumentParser(description='뉴스 수집 → 정제 → AI 요약·분석 → 리포트·내보내기')
    root.add_argument('--config', default=str(Path(__file__).resolve().parents[1] / 'config.json'), help='설정 JSON 경로 (서브커맨드 앞에 지정)')
    commands = root.add_subparsers(dest='command', required=True)
    p = commands.add_parser('fetch', help='RSS 또는 웹 크롤링으로 원본 수집')
    p.add_argument('--source', default='nasa')
    p.add_argument('--method', choices=['rss', 'crawl'], default='rss')
    p.add_argument('--limit', type=positive, default=10)
    p = commands.add_parser('clean', help='검증·정규화·중복 처리')
    p.add_argument('--duplicate-policy', choices=['skip', 'upsert'])
    p.add_argument('--limit', type=positive)
    for name, description in [('summarize', '기사별 AI 요약'), ('analyze', '종합 AI 분석'), ('report', '콘솔·파일 리포트와 PNG 차트'), ('export', 'CSV·Excel 내보내기')]:
        p = commands.add_parser(name, help=description)
        p.add_argument('--category')
        p.add_argument('--date', type=iso_date, help='발행일 UTC')
        p.add_argument('--date-from', type=iso_date)
        p.add_argument('--date-to', type=iso_date)
        if name == 'summarize':
            group = p.add_mutually_exclusive_group()
            group.add_argument('--all', action='store_true')
            group.add_argument('--id', type=positive)
            group.add_argument('--unsummarized', action='store_true')
            p.add_argument('--force', action='store_true', help='기존 요약도 다시 생성 (추가 API 호출)')
        if name in ('summarize', 'analyze'):
            p.add_argument('--limit', type=positive)
        if name == 'report':
            p.add_argument('--top', type=positive, default=5)
            p.add_argument('--format', choices=['md', 'txt'], default='md')
        if name == 'export':
            p.add_argument('--format', choices=['csv', 'excel'], required=True)
            p.add_argument('--status', choices=['summarized', 'unsummarized'])
    return root


def make_filters(args):
    exact = getattr(args, 'date', None)
    start, end = getattr(args, 'date_from', None), getattr(args, 'date_to', None)
    if exact and (start or end):
        raise ValueError('--date와 --date-from/--date-to는 동시에 사용할 수 없습니다.')
    start, end = exact or start, exact or end
    if start and end and start > end:
        raise ValueError('시작일은 종료일보다 늦을 수 없습니다.')
    return {k: v for k, v in [('date_from', start), ('date_to', end), ('category', getattr(args, 'category', None))] if v}


def main(argv=None):
    args = parser().parse_args(argv)
    store = None
    try:
        config = load_config(args.config)
        configure_logging(config)
        filters = make_filters(args)
        store = Store(config['database'])
        if args.command == 'fetch':
            from .collectors import fetch
            result = fetch(store, config, args.source, args.method, args.limit)
            return 1 if result['failed'] else 0
        if args.command == 'clean':
            from .cleaning import clean
            result = clean(store, args.duplicate_policy or config.get('duplicate_policy', 'skip'), args.limit)
            return 1 if result['invalid'] else 0
        if args.command == 'summarize':
            from .ai import summarize
            if args.unsummarized and args.force:
                raise ValueError('--unsummarized와 --force는 동시에 사용할 수 없습니다.')
            result = summarize(store, config, filters, article_id=args.id, limit=args.limit, force=args.force)
            return 1 if result['failed'] else 0
        if args.command == 'analyze':
            from .ai import analyze
            analysis_id, result = analyze(store, config, filters, args.limit)
            print(json.dumps({'analysis_id': analysis_id, **result}, ensure_ascii=False, indent=2))
        if args.command == 'report':
            from .reporting import report
            result, path = report(store, config, filters, args.top, args.format)
            print(result)
            logging.info('리포트 저장: %s', path)
        if args.command == 'export':
            from .exporting import export
            path, count = export(store, config, filters, args.format, args.status)
            logging.info('내보내기 완료 %s건: %s', count, path)
        return 0
    except (ValueError, OSError, KeyError, TypeError, sqlite3.Error) as exc:
        logging.error('%s', exc)
        return 1
    finally:
        if store:
            store.close()
