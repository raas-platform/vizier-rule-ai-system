"""
요청의 실제 클라이언트 IP 판별 (CloudFront 뒤에서 IP 기준 제한이 엣지 IP로 묶이지 않게).

규칙
- 기본: TCP 연결 상대 IP(request.client.host). X-Forwarded-For는 쓰지 않는다.
- TRUST_CLOUDFRONT=true 이고 요청이 CloudFront를 거친 것으로 판별될 때만
  X-Forwarded-For의 **마지막** IP를 클라이언트 IP로 쓴다.

왜 마지막 IP인가 (AWS 문서 "Request and response behavior for custom origins"):
  뷰어가 X-Forwarded-For를 이미 보냈으면 CloudFront는 뷰어 IP를 그 헤더 **끝에 덧붙여**
  오리진으로 보낸다. 예) 뷰어가 `192.0.2.4,192.0.2.3`을 보내면 오리진은
  `192.0.2.4,192.0.2.3,192.0.2.2`를 받는다. 앞쪽 값은 뷰어가 마음대로 쓸 수 있으므로,
  CloudFront가 직접 본 뷰어 IP는 마지막 값이다.

CloudFront를 거쳤는지 판별:
  1) CLOUDFRONT_ORIGIN_SECRET이 있으면: CloudFront 오리진 사용자 지정 헤더
     (CLOUDFRONT_ORIGIN_SECRET_HEADER, 기본 X-Origin-Verify) 값이 일치할 때만.
     AWS가 권장하는 방식(무작위 헤더 값을 비밀처럼 다룸). 운영 권장.
  2) 없으면: CloudFront가 오리진 요청에 붙이는 X-Amz-Cf-Id 헤더가 있을 때.
     이 헤더는 직접 접속으로도 위조할 수 있으므로 약한 판별이다
     (보안그룹을 CloudFront 전용으로 좁히지 않은 동안은 1)을 쓸 것).
"""

import hmac
import ipaddress
from typing import Optional

from fastapi import Request

from ..config import settings


def _valid_ip(text: str) -> Optional[str]:
    text = (text or "").strip()
    if not text:
        return None
    try:
        return str(ipaddress.ip_address(text))
    except ValueError:
        return None


def is_via_cloudfront(request: Request) -> bool:
    """요청이 CloudFront를 거쳤는지 (TRUST_CLOUDFRONT가 꺼져 있으면 항상 False)."""
    if not settings.trust_cloudfront:
        return False
    secret = settings.cloudfront_origin_secret
    if secret:
        header_name = settings.cloudfront_origin_secret_header or "X-Origin-Verify"
        got = request.headers.get(header_name)
        if got is None:
            return False
        return hmac.compare_digest(got.encode("utf-8"), secret.encode("utf-8"))
    return bool(request.headers.get("X-Amz-Cf-Id"))


def get_client_ip(request: Request) -> str:
    """IP 기준 제한에 쓸 클라이언트 IP."""
    peer = request.client.host if request.client else "unknown"
    if not is_via_cloudfront(request):
        return peer
    forwarded = request.headers.get("X-Forwarded-For", "")
    parts = [p for p in forwarded.split(",") if p.strip()]
    if not parts:
        return peer
    return _valid_ip(parts[-1]) or peer
