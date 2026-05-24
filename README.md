# AI Monitor

Mac mini, home server, remote workstation 같은 개발 머신에서 실행 중인 AI 작업을 브라우저로 확인하는 로컬 대시보드입니다.

Codex, Gemini, Claude 작업을 프로젝트 폴더별로 모아 보고, 선택한 작업의 최근 대화 흐름을 빠르게 확인할 수 있습니다.

## Features

- 실행 중인 `codex`, `gemini`, `claude` 작업 감지
- 폴더 기준 그룹핑
- 실행 중 / 종료됨 상태 구분
- 종료된 작업 표시 토글
- 사용자 질문과 AI 답변을 분리한 대화 기록 보기
- VPN, Tailscale, SSH tunnel 환경에서 접속 가능한 웹 UI

## Requirements

- macOS 또는 Unix 계열 개발 머신
- Python 3.9+
- `tmux`
- 브라우저에서 접근 가능한 로컬/VPN 네트워크

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

원격 머신의 VPN IP로 접속하려면:

```bash
python3 server.py --host 0.0.0.0 --port 8787
```

브라우저에서 엽니다.

```text
http://<your-vpn-ip>:8787
```

예:

```text
http://100.124.152.52:8787
```

로컬 머신에서만 확인하려면:

```bash
python3 server.py --host 127.0.0.1 --port 8787
```

그리고 브라우저에서:

```text
http://127.0.0.1:8787
```

## Usage

1. 개발 머신에서 Codex, Gemini, Claude 작업을 평소처럼 실행합니다.
2. AI Monitor 서버를 실행합니다.
3. 브라우저에서 대시보드를 엽니다.
4. 왼쪽에서 폴더를 선택합니다.
5. 가운데에서 작업을 선택합니다.
6. 오른쪽에서 해당 작업의 대화 기록을 확인합니다.

기본 화면은 실행 중인 작업만 보여줍니다. 종료된 작업도 보고 싶으면 `종료 포함`을 켜세요.

## Remote Access

Mac mini나 원격 개발 머신에서 쓰는 경우, 서버는 원격 머신에서 실행해야 합니다.

```bash
python3 server.py --host 0.0.0.0 --port 8787
```

그다음 VPN IP 또는 터널 주소로 접속합니다.

Tailscale 같은 VPN을 쓰고 있다면:

```text
http://<tailscale-ip>:8787
```

SSH tunnel을 쓰고 싶다면 로컬 컴퓨터에서:

```bash
ssh -L 8787:127.0.0.1:8787 <user>@<remote-host>
```

원격 머신에서는:

```bash
python3 server.py --host 127.0.0.1 --port 8787
```

로컬 브라우저에서는:

```text
http://127.0.0.1:8787
```

## Test

```bash
python3 -m unittest
python3 -m py_compile scanner.py server.py
```

HTML 스크립트 문법만 확인하려면:

```bash
node -e "const fs=require('fs'); const html=fs.readFileSync('index.html','utf8'); const m=html.match(/<script>([\\s\\S]*)<\\/script>/); new Function(m[1]);"
```

## Security

이 도구는 실행 중인 프로세스, 프로젝트 경로, AI 작업 대화 기록을 보여줍니다.

공개 인터넷에 직접 노출하지 마세요. VPN, Tailscale, SSH tunnel, 또는 인증이 있는 사설 네트워크 안에서 사용하는 것을 권장합니다.
