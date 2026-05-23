# AI Monitor

Mac mini 같은 원격 개발 머신에서 실행 중인 AI 작업을 브라우저로 확인하는 로컬 대시보드입니다.

현재 지원 범위:

- `codex`, `gemini`, `claude` 프로세스 감지
- tmux pane 내부에서 실행 중인 AI 작업 감지
- tmux 작업의 최근 화면 미리보기
- 프로젝트 폴더 기준 그룹핑
- tmux 세션으로 돌아가기 위한 명령 복사
- VPN 또는 SSH tunnel 환경에서 접근 가능한 웹 UI

## 실행

```bash
python3 server.py --host 0.0.0.0 --port 8787
```

브라우저에서 VPN IP로 접속합니다.

```text
http://<mac-mini-vpn-ip>:8787
```

로컬에서만 열려면:

```bash
python3 server.py --host 127.0.0.1 --port 8787
```

## 테스트

```bash
python3 -m unittest test_scanner.py
python3 -m py_compile scanner.py server.py
```

## 보안 메모

이 앱은 실행 중인 프로세스, 프로젝트 경로, tmux 화면 일부를 보여줍니다. 공개 인터넷에 직접 열지 말고 VPN, SSH tunnel, 또는 인증이 있는 터널 뒤에서 사용하세요.
