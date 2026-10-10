"""Human-readable reports with explicitly scoped metrics and analysis provenance."""
import json
import hashlib
import os
from collections import Counter
from pathlib import Path

from .storage import now


def configure_font(config):
    # Use a writable local cache on read-only hosts and headless CI.
    os.environ.setdefault('MPLCONFIGDIR', str(Path(config['output_dir']) / '.matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import font_manager, rcParams
    if config.get('font_path'):
        font_manager.fontManager.addfont(config['font_path'])
        font = font_manager.FontProperties(fname=config['font_path']).get_name()
    else:
        available = {f.name for f in font_manager.fontManager.ttflist}
        font = next((name for name in ['AppleGothic', 'Malgun Gothic', 'NanumGothic', 'Noto Sans CJK KR', 'Noto Sans KR'] if name in available), None)
    if not font:
        raise ValueError('한글 폰트를 찾을 수 없습니다. config.json의 font_path에 한글 TTF/OTF 경로를 설정하세요.')
    rcParams['font.family'] = font
    rcParams['axes.unicode_minus'] = False


def charts(config, articles, output):
    configure_font(config)
    import matplotlib.pyplot as plt
    counts = Counter(a['category'] for a in articles)
    dates = Counter(a['collected_at'][:10] for a in articles)
    specs = [('categories.png', counts.most_common(), '카테고리별 뉴스 수', '카테고리'),
             ('collection_trend.png', sorted(dates.items()), '일자별 수집 추이', '최초 수집일 (UTC)')]
    for filename, values, title, xlabel in specs:
        fig, ax = plt.subplots(figsize=(10, 5), layout='constrained')
        if values:
            labels, amounts = zip(*values)
            if filename == 'categories.png':
                ax.bar(labels, amounts, color='#287b91')
            else:
                ax.plot(labels, amounts, marker='o', color='#287b91')
            ax.tick_params(axis='x', rotation=35)
            from matplotlib.ticker import MaxNLocator
            ax.yaxis.set_major_locator(MaxNLocator(integer=True))
            ax.set_ylim(bottom=0)
        else:
            ax.text(0.5, 0.5, '데이터 없음', ha='center', va='center', transform=ax.transAxes)
        ax.set(title=title, xlabel=xlabel, ylabel='뉴스 수 (건)')
        fig.savefig(output / filename, dpi=150)
        plt.close(fig)
    return [s[0] for s in specs]


def metrics(store, articles):
    counts = dict(store.db.execute('SELECT clean_status,COUNT(*) FROM raw_news GROUP BY clean_status'))
    processed = sum(v for k, v in counts.items() if k != 'pending')
    invalid = counts.get('invalid', 0)
    duplicates = counts.get('duplicate', 0) + counts.get('updated', 0)
    return {
        'raw_total': sum(counts.values()), 'processed': processed, 'pending': counts.get('pending', 0),
        'invalid_rate': invalid / processed if processed else 0,
        'duplicate_rate': duplicates / processed if processed else 0,
        'summary_rate': sum(a['summary'] is not None for a in articles) / len(articles) if articles else 0,
    }


def report(store, config, filters, top=5, format='md'):
    articles = store.articles(filters)
    output = Path(config['output_dir'])
    output.mkdir(parents=True, exist_ok=True)
    # Distinct snapshots must not overwrite assets referenced by another report.
    fingerprint = hashlib.sha256(json.dumps(articles, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
    chart_dir = output / 'charts' / fingerprint
    chart_dir.mkdir(parents=True, exist_ok=True)
    chart_files = [str((chart_dir / name).relative_to(output)) for name in charts(config, articles, chart_dir)]
    quality = metrics(store, articles)
    lines = ['# AI 뉴스 종합 리포트', '', f'생성 시각: {now()}',
             f'필터 (발행일 UTC): {json.dumps(filters, ensure_ascii=False)}', f'대상 뉴스: {len(articles)}건', '',
             '## 품질 지표', '',
             f"- 원본 수집: {quality['raw_total']}건 / 정제 처리: {quality['processed']}건 / 대기: {quality['pending']}건",
             f"- 정제 거부율 (필수 필드 누락·잘못된 날짜/URL): {quality['invalid_rate']:.1%}",
             f"- 중복률 (skip 및 upsert 포함): {quality['duplicate_rate']:.1%}",
             f"- 요약 완료율: {quality['summary_rate']:.1%}",
             '- 정제 거부율·중복률은 전체 raw 처리 건수 기준, 요약 완료율은 현재 필터의 clean 뉴스 기준입니다.',
             '- 분모가 0인 지표는 0.0%로 표시합니다.', '', f'## TOP {top} 카테고리', '']
    lines.extend(f'- {category}: {count}건' for category, count in Counter(a['category'] for a in articles).most_common(top))
    if not articles:
        lines.append('- 데이터 없음')
    lines += ['', '## AI 인사이트', '']
    analysis = store.latest_analysis(filters)
    if analysis:
        snapshot = json.loads(analysis['snapshot'])
        current = {a['id']: a for a in articles}
        stale = any(a['id'] not in current or any(current[a['id']][k] != a[k] for k in ('title', 'body', 'category', 'published_at', 'summary')) for a in snapshot)
        lines += [f"분석 ID: {analysis['id']} / 생성: {analysis['created_at']} / 모델: {analysis['model']}",
                  f'분석 표본: {len(snapshot)}건 / 현재 대상: {len(articles)}건',
                  '기사 ID: ' + ', '.join(str(a['id']) for a in snapshot)]
        if stale or len(snapshot) != len(articles):
            lines.append('주의: 현재 데이터와 분석 표본이 다릅니다. analyze를 다시 실행해 최신 분석을 생성하세요.')
        result = json.loads(analysis['result'])
        for key, label in [('trends', '주요 트렌드'), ('keywords', '핵심 키워드'), ('implications', '시사점')]:
            lines += ['', f'### {label}'] + [f'- {v}' for v in result[key]]
    else:
        lines.append('동일한 기간·카테고리 조건으로 저장된 AI 분석이 없습니다. analyze를 먼저 실행하세요.')
    lines += ['', '## 차트', '', '중복 제거한 뉴스의 최초 수집일(UTC)을 집계합니다. 날짜 필터는 발행일에 적용됩니다.']
    lines += [f'![{name}]({name})' if format == 'md' else f'차트: {name}' for name in chart_files]
    lines += ['', '## 기사 출처', '']
    lines += [f"- [{a['id']}] {a['title']} | {a['url']}" for a in articles]
    result = '\n'.join(lines) + '\n'
    if format == 'txt':
        result = '\n'.join(line.lstrip('# ') if line.startswith('#') else line for line in result.splitlines()) + '\n'
    path = output / f'report.{format}'
    path.write_text(result, encoding='utf-8')
    return result, path
