# AI 뉴스 트렌드 및 종합 분석 리포트

Python 3.10 이상에서 실행하는 CLI 과제입니다. 뉴스 원문을 수집하고 SQLite에 저장한 뒤 정제, AI 요약, 종합 분석, 한글 차트와 리포트, CSV/Excel 내보내기를 수행합니다.

**필수 기능만 구현했습니다.** 웹 UI, list/show 조회 명령, 감성 분석, 정기 실행 스케줄링은 포함하지 않습니다.

## 1. 설치

프로젝트 폴더에서 실행합니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python main.py --help
```

Windows에서는 가상환경 활성화 명령으로 `.venv\Scripts\activate`를 사용합니다. 실행만 필요하면 `requirements.txt`를 설치합니다. `requirements-lock.txt`는 개발 환경(Python 3.13/macOS)에서 검증한 정확한 버전 기록입니다.

## 2. API 키 없이 가능한 작업

기본 소스는 NASA입니다. RSS로 기사 주소를 발견하는 방식과 HTML 뉴스 목록에서 보도자료(`news-release`) 주소를 찾는 크롤링 방식을 별도로 제공합니다. 양쪽 모두 기사 페이지의 **본문**을 가져옵니다. `--limit`은 최대 시도 건수이며 목록에 기사가 적으면 그보다 적게 수집합니다.

```bash
python main.py fetch --source nasa --method rss --limit 5
python main.py fetch --source nasa --method crawl --limit 5
python main.py clean
python main.py report
python main.py export --format csv
python main.py export --format excel
```

- RSS와 크롤링으로 같은 기사를 가져와도 clean 뉴스는 URL 기준으로 중복 제거됩니다.
- `raw_news`에는 기사 HTML 원본, RSS 항목(해당 시), 추출 필드, 소스, 수집 방식, UTC 수집 시각을 보존합니다.
- 요약과 분석을 아직 실행하지 않은 리포트에는 **AI 분석 없음**이 명시됩니다. 가짜 요약·분석을 생성하지 않습니다.
- 수집한 뉴스의 언어는 원문에 따릅니다. 기본 소스의 뉴스는 주로 영어이며 AI 요약·분석 결과는 한국어로 요청합니다.

## 3. 실제 AI 요약과 분석

[Google AI Studio](https://aistudio.google.com/apikey)에서 발급받은 Gemini API 키를 로컬 환경변수에 설정합니다. macOS 기본 zsh 터미널에서는 아래 명령을 한 줄씩 실행하세요. 첫 번째 명령 후 키를 입력하고 Enter를 누른 다음 두 번째 명령을 실행합니다. 입력은 표시되지 않으며 코드나 설정 파일에 키를 넣을 필요가 없습니다.

```bash
read -s GEMINI_API_KEY
export GEMINI_API_KEY
```

환경변수는 현재 터미널과 그 터미널에서 실행한 프로그램에 적용됩니다. 새 터미널에서는 다시 설정해야 합니다. 현재 프로그램은 `.env` 파일을 자동으로 읽지 않습니다.

`config.json`은 Gemini의 OpenAI 호환 API를 사용하도록 설정되어 있습니다. API 요청은 Google 서버로 전송되며 OpenAI API 키는 필요하지 않습니다.

```json
"ai": {
  "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
  "model": "gemini-2.5-flash",
  "api_key_env": "GEMINI_API_KEY",
  "api_key": "",
  "timeout": 60,
  "max_input_chars": 50000
}
```

`gemini-2.5-flash`는 [공식 가격표](https://ai.google.dev/gemini-api/docs/pricing)에 무료 티어가 안내되어 있습니다. Google AI Studio에서 프로젝트의 무료 티어 적용 여부와 사용 가능한 할당량을 확인하세요. 모델 이름만으로 무료 사용이 보장되지는 않으며, 유료 티어에서는 요금이 발생할 수 있습니다. 사용량 제한으로 HTTP 429가 발생하면 로그를 확인하고 할당량이 회복된 뒤 재실행하세요. 먼저 `--limit 1`로 한 건을 확인할 수 있습니다.

```bash
python main.py summarize --unsummarized --limit 5
python main.py analyze
python main.py report
python main.py export --format csv --status summarized
python main.py export --format excel --status summarized
```

- `summarize --all`: 전체 대상을 검사하되 이미 요약된 기사는 기본 스킵합니다.
- `summarize --id 1`: 특정 기사 한 건을 선택합니다. ID는 CSV/Excel에서 확인할 수 있습니다.
- `summarize --unsummarized`: 미요약 기사만 선택합니다. 옵션을 생략해도 이 동작입니다.
- `summarize --all --force`: 기존 요약을 다시 생성합니다. 추가 API 호출이 발생합니다.
- 한 건의 API 실패는 로그에 남기고 다음 기사를 계속 처리합니다. 실패한 기사는 미요약 상태로 남아 재실행할 수 있습니다.
- 분석에는 주요 트렌드·핵심 키워드·시사점이 포함됩니다. 잘못된 JSON, 빈 결과, 미완료 응답은 저장하지 않습니다.
- 입력 전체가 `ai.max_input_chars`를 초과하면 본문을 조용히 잘라내지 않고 오류를 알립니다. 먼저 요약하거나 `--limit`/기간 필터로 대상을 줄이세요.

## 4. 필터 및 명령 예시

날짜 필터는 **발행일 UTC 기준**, 시작일·종료일을 모두 포함합니다. `--date`와 범위 옵션을 함께 사용할 수 없습니다. 카테고리는 원문에서 수집한 문자열과 정확히 일치해야 합니다. CSV에서 값을 확인하세요.

```bash
python main.py summarize --unsummarized --date 2026-10-07
python main.py analyze --date-from 2026-10-01 --date-to 2026-10-07
python main.py report --date-from 2026-10-01 --date-to 2026-10-07 --top 3
python main.py report --format txt
python main.py export --format excel --category "과학·우주"
python main.py clean --duplicate-policy upsert
```

리포트는 **동일한 날짜·카테고리 필터**로 저장한 최신 분석을 읽습니다. 기간 분석을 만든 경우 리포트에도 같은 기간을 지정하세요. 저장된 분석의 기사 내용이나 표본 수가 현재 데이터와 다르면 재분석 안내를 표시합니다. `--limit` 분석은 최신 발행일 순으로 선택하며 분석에 사용한 ID와 표본 수를 저장합니다.

`clean`은 아직 처리하지 않은 raw만 처리합니다. 이미 처리한 raw를 설정 변경으로 재처리하지 않습니다. 최신 기사로 갱신하려면 **fetch를 다시 실행한 뒤** `clean --duplicate-policy upsert`를 실행하세요. 내용·제목·분류·발행일이 바뀌면 기존 요약을 제거합니다. 동일한 내용은 요약을 유지합니다.

## 5. 설정

설정은 `config.json`으로 관리합니다. API 키는 환경변수가 설정 파일보다 우선합니다. 개인 설정은 `config.local.json`으로 복사하고 다음과 같이 사용하세요.

```bash
python main.py --config config.local.json fetch --source nasa --limit 3
```

`--config`는 **서브커맨드 앞**에 둡니다. database/output_dir/log_file/font_path의 상대 경로는 설정 파일의 위치를 기준으로 해석합니다.

| 설정 | 역할 |
|---|---|
| database | SQLite 영구 저장소 경로 |
| output_dir / log_file | 결과물 폴더 / 로그 파일 |
| duplicate_policy | skip 또는 upsert |
| request_timeout / request_delay | 뉴스 요청 타임아웃 / 요청 사이 최소 지연(초) |
| sources | 소스별 rss_url, crawl_url, link_selector, body_selector, 기본 category |
| font_path | 한글 TTF/OTF 파일 경로. 빈 값이면 OS 폰트 자동 탐색 |
| ai.base_url / model | Gemini OpenAI 호환 API 주소 / 기본 gemini-2.5-flash |
| ai.api_key_env / api_key | 기본 GEMINI_API_KEY 환경변수 / 선택적인 키 직접 설정 |
| ai.timeout / max_input_chars | AI 요청 타임아웃(초) / 입력 JSON 최대 문자 수 |

실제 키를 포함한 파일을 제출하거나 커밋하지 마세요. `config.local.json`, DB, 출력물, 로그, 가상환경은 `.gitignore`에서 제외했습니다.

**한글 폰트:** macOS AppleGothic, Windows Malgun Gothic, Linux NanumGothic 또는 Noto Sans 계열을 탐색합니다. 찾지 못하면 오류를 알립니다. 한글 폰트를 설치하거나 `font_path`를 지정한 뒤 다시 실행하세요.

## 6. 결과물과 데이터 규칙

| 파일/테이블 | 내용 |
|---|---|
| data/news.db → raw_news | 변경하지 않는 원문 payload + 정제 상태/오류 |
| data/news.db → clean_news | URL 기준 최신 정제 기사와 요약 |
| data/news.db → analyses | 분석 결과, 모델, 필터, 입력 기사 스냅샷 |
| output/report.md 또는 report.txt | 콘솔과 동일한 리포트 |
| output/charts/스냅샷ID/*.png | 카테고리별 기사 수, 최초 수집일별 추이 |
| output/news.csv / news.xlsx | 필터링한 기사 데이터 |
| logs/news.log | INFO/WARNING/ERROR 실행 로그 |

같은 형식의 리포트와 내보내기를 재실행하면 파일을 갱신합니다. 여러 결과를 보관하려면 출력 폴더를 바꾸거나 결과물을 복사하세요. 차트는 데이터 스냅샷별 경로에 저장하므로 다른 범위의 TXT 리포트를 생성해도 기존 MD의 차트가 바뀌지 않습니다.

정제 규칙:

- 필수: 제목, 본문, 유효한 HTTP(S) URL, 해석 가능한 발행일. 누락/오류 데이터는 raw에 남기고 clean에서 제외합니다.
- 카테고리 결측은 `미분류`로 처리합니다.
- HTML·스크립트를 제거하고 유니코드/공백을 정규화합니다.
- 날짜는 UTC ISO 8601로 통일합니다. 타임존 없는 날짜는 UTC로 간주합니다.
- URL의 fragment와 `utm_*`, `fbclid`, `gclid` 추적 파라미터를 제거합니다. 의미 있는 쿼리 파라미터는 보존합니다.

품질 지표:

- **정제 거부율** = invalid raw / 처리 완료 raw. 필수 필드·URL·날짜 오류를 포함합니다.
- **중복률** = (duplicate + updated raw) / 처리 완료 raw.
- **요약 완료율** = 요약 있는 clean / 현재 필터의 clean.
- 앞의 두 지표는 전체 raw 기준이며 리포트의 기간 필터와 별개임을 표시합니다. 처리 대기 raw는 분모에서 제외합니다. 분모가 0이면 0.0%입니다.
- TOP N은 카테고리별 뉴스 수 집계입니다.
- 수집 추이는 현재 필터에 포함된 중복 제거 기사의 **최초 수집일 UTC**를 기준으로 그립니다.

CSV는 Excel에서 한글을 읽기 쉽도록 UTF-8 BOM으로 저장합니다. CSV/Excel에서 수식으로 실행될 수 있는 원문은 텍스트로 이스케이프합니다. Excel의 셀 길이 한도를 넘으면 오류를 내고 CSV 사용을 안내합니다.

## 7. 테스트

```bash
python -m pytest -q
```

테스트는 임시 SQLite와 로컬 HTTP 서버를 사용합니다. 외부 뉴스/AI 서버 응답만 대체하며 실제 CLI를 별도 프로세스로 실행합니다. 실제 API 키나 결제는 필요하지 않습니다. 테스트용 응답은 테스트 파일에만 존재합니다.

테스트 범위: 전체 파이프라인, 영구 저장, RSS/크롤링, URL 중복, 변경 시 요약 무효화, 실패 후 재시도, robots 금지, HTTP 오류, 잘못된 AI 응답 후 계속 처리, 날짜/카테고리 필터, 빈 데이터, 리포트 차트 보존, 정제 품질 지표, 수식 이스케이프.

로컬 서버를 열 수 없는 샌드박스에서는 네트워크 권한을 허용한 터미널에서 실행해야 합니다.

종료 코드: 성공 `0`, 처리 중 실패 또는 설정/네트워크 오류 `1`, 잘못된 CLI 인자 `2`. 일부 기사가 실패해도 성공한 데이터는 저장됩니다. WARNING/ERROR 로그로 실패 원인을 확인하세요.

## 8. 학습 설명과 요구사항 대응

- RSS/API는 구조가 일정해 추출하기 쉽지만 제공 필드·분량에 제한이 있습니다. 크롤링은 페이지 본문을 읽을 수 있지만 HTML 변경에 취약합니다.
- raw는 원문 확인과 오류 추적에, clean은 검색·분석에 사용합니다. 원본을 덮어쓰지 않아 정제 오류를 점검할 수 있습니다.
- AI 흐름은 DB 조회 → 데이터와 프롬프트 구성 → 타임아웃이 있는 HTTP 요청 → 응답 검증 → DB 저장입니다.
- 차트는 clean 데이터를 Counter로 집계한 뒤 matplotlib으로 PNG에 저장합니다.
- 분석을 별도 저장하므로 report는 API를 재호출하지 않습니다. 나중에 모델이 달라져도 당시 입력과 결과를 확인할 수 있습니다.

모듈: `cli.py`(명령), `config.py`(설정·로그), `storage.py`(저장), `collectors.py`(수집), `cleaning.py`(정제), `ai.py`(요약·분석), `reporting.py`(리포트·차트), `exporting.py`(내보내기).

## 9. 뉴스 수집 정책 및 참고 문서

기본 소스 선정 시 [NASA robots.txt](https://www.nasa.gov/robots.txt)와 [NASA 사용 지침](https://www.nasa.gov/nasa-brand-center/images-and-media/)을 확인했습니다. 원문 출처를 보존하고 학습용으로 소량 수집합니다. 이미지·로고는 수집하지 않습니다. 원문에 제3자 권리 표시가 있는 경우 해당 제한을 따르세요.

프로그램은 각 호스트의 robots.txt를 확인하고 요청 간 지연을 적용합니다. robots 확인 실패(404 제외), 금지 URL, 과도한 리다이렉트는 수집하지 않습니다. HTTP 리다이렉트 목적지도 다시 확인합니다. 크롤링 목록은 같은 호스트의 링크만 따라갑니다. 새 소스를 추가할 때에는 해당 사이트의 이용 조건도 별도로 확인해야 합니다.

- [NASA RSS](https://www.nasa.gov/feed/)
- [NASA 뉴스 목록](https://www.nasa.gov/news/all-news/)
- [Gemini OpenAI 호환 API](https://ai.google.dev/gemini-api/docs/openai)
- [Gemini API 키 발급](https://aistudio.google.com/apikey)
- [Gemini API 가격 및 무료 티어](https://ai.google.dev/gemini-api/docs/pricing)
