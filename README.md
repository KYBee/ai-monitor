# AI Monitor

실행 중인 AI 에이전트 작업을 브라우저에서 확인하는 로컬 대시보드입니다.

Codex, Gemini, Claude 같은 CLI 에이전트 작업을 폴더별로 모아 보고, 선택한 작업의 대화 기록을 빠르게 확인할 수 있습니다.

## Features

- 실행 중인 `codex`, `gemini`, `claude` 작업 감지
- 폴더 기준 그룹핑
- 실행 중 / 종료됨 상태 구분
- 종료된 작업 표시 토글
- 사용자 질문과 AI 답변을 분리한 대화 기록 보기

## Requirements

- Python 3.9+
- `tmux`
- 로컬 브라우저

추가 Python 패키지는 필요 없습니다. 표준 라이브러리만 사용합니다.

## Install

```bash
git clone git@github.com:KYBee/ai-monitor.git
cd ai-monitor
```

HTTPS를 선호하면:

```bash
git clone https://github.com/KYBee/ai-monitor.git
cd ai-monitor
```

## Run

```bash
python3 server.py --host 127.0.0.1 --port 8787
```

브라우저에서 엽니다.

```text
http://127.0.0.1:8787
```

## Usage

1. Codex, Gemini, Claude 작업을 평소처럼 실행합니다.
2. AI Monitor 서버를 실행합니다.
3. 브라우저에서 대시보드를 엽니다.
4. 왼쪽에서 폴더를 선택합니다.
5. 가운데에서 작업을 선택합니다.
6. 오른쪽에서 해당 작업의 대화 기록을 확인합니다.

기본 화면은 실행 중인 작업만 보여줍니다. 종료된 작업도 보고 싶으면 `종료 포함`을 켜세요.

## Test

```bash
python3 -m unittest
python3 -m py_compile scanner.py server.py
```

HTML 스크립트 문법만 확인하려면:

```bash
node -e "const fs=require('fs'); const html=fs.readFileSync('index.html','utf8'); const m=html.match(/<script>([\\s\\S]*)<\\/script>/); new Function(m[1]);"
```
