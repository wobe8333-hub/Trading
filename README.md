## Trading Project

이 프로젝트는 단계별 로드맵에 따라 구현되는 트레이딩 시스템입니다.

### 기본 구조

- `config/` 시스템 전체 설정 파일
- `src/` 애플리케이션 소스 코드
- `tests/` 테스트 코드
- `data/` 데이터/캐시 디렉토리
- `logs/` 로그 디렉토리

### 실행 방법

1. 파이썬 의존성 설치
   ```bash
   pip install -r requirements.txt
   ```

2. 설정 시스템 검증 실행
   ```bash
   python -m pytest tests/unit/test_config_loader.py
   ```

3. 메인 엔트리포인트 실행
   ```bash
   python -m src.app.main
   ```

