# 요구사항 및 검증 기록

검증일: 2026-10-07

| 요구사항 | 구현 | 검증 |
|---|---|---|
| argparse 6개 서브커맨드 | cli.py | CLI 통합 테스트, --help |
| RSS와 크롤링 두 방식 | collectors.py | 로컬 HTTP 통합 테스트 + 실제 NASA 각 3건 성공 |
| timeout·오류·요청 지연·robots | collectors.py | HTTP 503, robots 금지, 실제 수집 |
| raw/clean 분리 및 영구 저장 | storage.py | SQLite 재실행, integrity_check=ok |
| 필수 필드·공백·날짜·결측·중복 | cleaning.py | 정제 거부/중복 지표, skip/upsert 회귀 테스트 |
| AI 요약 옵션, 실패 후 계속 | ai.py / cli.py | HTTP 429, 잘못된 응답, limit, 기존 요약 스킵 테스트 |
| AI 종합 분석 저장 | ai.py / storage.py | 테스트 API로 3개 항목 결과·입력 스냅샷 저장 |
| 한글 matplotlib PNG 2종 | reporting.py | 실제 뉴스 5건 차트 생성 및 시각 확인 |
| 품질 지표·TOP N·AI 리포트 | reporting.py | MD/TXT, 빈 데이터, 오래된 분석 표시, 차트 보존 테스트 |
| CSV/Excel 및 summarized 필터 | exporting.py | 생성 파일 재열기, 5건 일치, 필터·수식 이스케이프 테스트 |
| 설정과 INFO/WARNING/ERROR 로그 | config.py | 기본/임시 설정 파일, 실제 실행 로그 |
| 4개 이상 모듈 | news_pipeline 패키지 | 8개 기능 모듈 |

## 실제 수집 결과

- RSS: 3건 성공, 0건 실패
- 크롤링: 3건 성공, 0건 실패
- 정제: 신규 5건, 중복 1건, 거부 0건
- SQLite 무결성: 정상
- CSV와 Excel: 각각 기사 5건
- 예제 리포트: output/report.md
- 예제 AI 요약/분석: 미실행 (API 키 없음)

초기 라이브 테스트에서 NASA 발행일 `parsely-pub-date`와 메뉴/공모 페이지가 섞이는 문제가 확인되어 회귀 테스트와 함께 수정했다. 최종 크롤링 소스는 뉴스 목록의 보도자료 링크로 한정했다.

## 코드 리뷰 후 수정

- 잘못된 AI 응답의 choices 항목이 null일 때 전체 배치가 멈추던 문제: 형식 검증을 추가하고 실패 후 다음 기사 성공을 확인했다.
- 서로 다른 범위의 MD/TXT 리포트가 차트를 덮어쓰던 문제: 데이터 스냅샷별 차트 경로로 분리하고 기존 PNG가 바뀌지 않음을 확인했다.

## 사용자 설정 후 남은 검증

현재 OPENAI_API_KEY가 설정되어 있지 않다. 실제 AI API의 계정 인증, 모델 접근 권한, 실제 요약·분석 품질은 아직 확인하지 않았다. 로컬 테스트 API를 통과한 것을 실제 서비스 검증으로 간주하지 않는다.

README의 API 키 설정 후 다음 순서로 실행한다.

```bash
python main.py summarize --unsummarized --limit 5
python main.py analyze
python main.py report
```

보너스 기능은 구현하지 않았다.

## 최종 자동 검증

- `.venv/bin/python -m pytest -q --tb=short`: **14 passed in 59.12s**
- `.venv/bin/python -m compileall -q main.py news_pipeline`: 성공
- 실제 생성 CSV/Excel 재열기: 각 5건, 본문 비어 있지 않음
- `PRAGMA integrity_check`: `ok`
