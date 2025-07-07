"""
로깅 설정 유틸리티
"""

import logging
import sys
from pathlib import Path


def setup_logger(name: str, level: str = "INFO") -> logging.Logger:
    """
    로거 설정

    Args:
        name: 로거 이름
        level: 로그 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        설정된 로거 인스턴스
    """
    logger = logging.getLogger(name)

    # 이미 핸들러가 설정되어 있으면 중복 설정 방지
    if logger.handlers:
        return logger

    # 로그 레벨 설정
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(log_level)

    # 포매터 설정
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 콘솔 핸들러
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 파일 핸들러 (로그 디렉토리가 있는 경우에만)
    log_dir = Path(__file__).parent.parent.parent / "logs"  # backend/logs
    try:
        log_dir.mkdir(exist_ok=True)
        file_handler = logging.FileHandler(log_dir / "app.log", encoding="utf-8")
        file_handler.setLevel(logging.INFO)  # 파일에 INFO 이상 기록 (강화된 로그 포함)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        # 파일 핸들러 생성 실패 시 콘솔에만 로그 출력
        console_handler.stream.write(f"Warning: Could not create file handler: {e}\n")

    # 프로파게이션 방지 (루트 로거로 전파 안 함)
    logger.propagate = False

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    로거 인스턴스 반환 (기존에 설정된 것이 있으면 재사용)

    Args:
        name: 로거 이름 (보통 __name__ 사용)

    Returns:
        로거 인스턴스
    """
    return setup_logger(name)
