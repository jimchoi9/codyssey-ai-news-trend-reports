# 필수 과제 구현 계획

범위: fetch, clean, summarize, analyze, report, export. 보너스 및 웹 UI 제외.

1. argparse CLI, config.json, logging, SQLite 기반 구성
2. RSS / BeautifulSoup 기사 수집, robots.txt 확인, timeout 및 요청 간 지연
3. raw/clean 분리, 필수 필드와 날짜 검증, URL 중복 skip/upsert
4. 실제 AI HTTP API 요약, 대상 선택, 실패 후 계속, 기존 요약 건너뛰기
5. 기간/카테고리 종합 분석, 트렌드·키워드·시사점 저장
6. 한글 matplotlib 차트 2종, 품질 지표·TOP N·AI 포함 MD/TXT, CSV/Excel
7. 통합 테스트, 실제 수집 검증, 실행 문서

설계 결정:
- SQLite 테이블: raw_news, clean_news, analyses. raw 항목마다 정제 결과를 기록해 재처리로 지표가 부풀지 않게 한다.
- 날짜 필터는 발행일 UTC 기준, 수집 추이 차트는 수집일 UTC 기준이다.
- upsert로 기사 내용이 바뀌면 기존 요약을 제거한다. 분석은 입력 스냅샷을 보존한다.
- 기본 뉴스 소스 NASA. 단일 소스 허용 요건에 맞춰 RSS와 사이트 크롤링 양쪽을 구현한다.
- CSV와 Excel을 지원해 문서 앞부분과 상세 요구사항을 함께 충족한다.
- AI 키는 환경변수 우선, 설정 파일 값은 선택. 실제 키는 저장소에 포함하지 않는다.
- 현재 폴더는 Git 저장소가 아니므로 이 폴더에서 구현하며 커밋/브랜치 생성은 하지 않는다.

검증: 로컬 테스트 HTTP 서버로 외부 뉴스/AI 응답만 대체하고 실제 CLI subprocess, SQLite, 파일 출력을 검증한다. 실제 AI 검증은 사용자 키 설정 후 수행한다.

완료 기록: 기본 구조, 두 수집 방식, 정제, AI 연동 코드, 분석 저장, 리포트/내보내기, 문서화 완료. 전체 14개 테스트 통과. 실제 NASA RSS/크롤링 각 3건 수집 성공. 상세 검증과 API 키가 필요한 후속 단계는 VALIDATION.md 참고.
