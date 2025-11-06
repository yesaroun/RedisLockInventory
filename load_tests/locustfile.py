"""
Locust load test scenarios for Version 1 (ROADMAP.md)

테스트 시나리오:
1. 기본 동시성 테스트: 100명이 동시에 1개씩 구매 (총 100개 재고)
2. 락 타임아웃 테스트: 락 홀딩 시간 초과 시 자동 해제
3. 블랙프라이데이 시나리오: 1000명이 100개 재고 경쟁

성능 목표:
- TPS: 100
- 응답시간: P50 < 100ms, P99 < 500ms
- 정확도: 100% (초과 판매 0건)
"""

import random
from typing import Dict, Optional

from locust import HttpUser, TaskSet, task, between, events


# 전역 메트릭 수집
oversold_count = 0
total_purchases = 0
failed_purchases = 0
stock_check_failures = 0


class InventoryTaskSet(TaskSet):
    """재고 관리 시스템 사용자 행동 모델"""

    def on_start(self):
        """각 사용자가 시작할 때 실행: 회원가입 및 로그인"""
        self.user_id = f"loadtest_user_{random.randint(1, 1000000)}"
        self.access_token: Optional[str] = None
        self.product_id: Optional[int] = None

        # 회원가입
        self._register()
        # 로그인
        self._login()

    def _register(self):
        """회원가입"""
        with self.client.post(
            "/api/auth/register",
            json={
                "username": self.user_id,
                "password": "test1234",
                "email": f"{self.user_id}@loadtest.com",
            },
            name="[Auth] Register",
            catch_response=True,
        ) as response:
            if response.status_code == 201:
                response.success()
            elif response.status_code == 400:
                # 이미 존재하는 사용자 (재시작 시)
                response.success()
            else:
                response.failure(f"Registration failed: {response.status_code}")

    def _login(self):
        """로그인 및 토큰 획득"""
        with self.client.post(
            "/api/auth/login",
            data={"username": self.user_id, "password": "test1234"},
            name="[Auth] Login",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get("access_token")
                response.success()
            else:
                response.failure(f"Login failed: {response.status_code}")

    def _get_headers(self) -> Dict[str, str]:
        """인증 헤더 반환"""
        if not self.access_token:
            return {}
        return {"Authorization": f"Bearer {self.access_token}"}

    @task(3)
    def check_stock(self):
        """재고 조회 (가장 빈번한 작업)"""
        if not self.product_id:
            return

        with self.client.get(
            f"/api/products/{self.product_id}/stock",
            headers=self._get_headers(),
            name="[Product] Check Stock",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                data = response.json()
                # 재고 불일치 감지
                if data.get("redis_stock", -1) != data.get("db_stock", -1):
                    global stock_check_failures
                    stock_check_failures += 1
                    response.failure("Stock mismatch detected!")
                else:
                    response.success()
            else:
                response.failure(f"Stock check failed: {response.status_code}")

    @task(2)
    def list_products(self):
        """상품 목록 조회"""
        with self.client.get(
            "/api/products",
            headers=self._get_headers(),
            name="[Product] List Products",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                products = response.json()
                if products and not self.product_id:
                    # 가장 최신 상품 ID 저장 (ID가 가장 큰 상품)
                    self.product_id = max(products, key=lambda x: x["id"])["id"]
                response.success()
            else:
                response.failure(f"List products failed: {response.status_code}")

    @task(5)
    def purchase_product(self):
        """상품 구매 (핵심 동시성 테스트)"""
        if not self.product_id:
            # 상품 ID가 없으면 먼저 목록 조회
            self.list_products()
            if not self.product_id:
                return

        global total_purchases, failed_purchases, oversold_count

        with self.client.post(
            "/api/purchases",
            json={"product_id": self.product_id, "quantity": 1},
            headers=self._get_headers(),
            name="[Purchase] Buy Product",
            catch_response=True,
        ) as response:
            if response.status_code == 201:
                total_purchases += 1
                # 성공 응답에서도 실제 재고 확인
                data = response.json()
                if data.get("remaining_stock", 0) < 0:
                    oversold_count += 1
                    response.failure("Negative stock detected! OVERSOLD!")
                else:
                    response.success()
            elif response.status_code == 400:
                # 재고 부족 (정상적인 실패)
                data = response.json()
                detail = data.get("detail", "")
                if "재고가 부족합니다" in detail or "Insufficient stock" in detail:
                    failed_purchases += 1
                    # 이것은 예상된 실패이므로 success로 처리
                    response.success()
                else:
                    response.failure(f"Purchase failed with unexpected error: {detail}")
            else:
                response.failure(f"Purchase failed: {response.status_code}")

    @task(1)
    def view_purchase_history(self):
        """구매 이력 조회"""
        with self.client.get(
            "/api/purchases/me",
            headers=self._get_headers(),
            name="[Purchase] My History",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Purchase history failed: {response.status_code}")


class NormalUser(HttpUser):
    """일반 사용자 (일반적인 쇼핑 행동)"""

    tasks = [InventoryTaskSet]
    wait_time = between(1, 3)  # 1-3초 대기
    host = "http://localhost:8080"


class AggressiveBuyer(HttpUser):
    """공격적인 구매자 (블랙프라이데이 시나리오)"""

    tasks = [InventoryTaskSet]
    wait_time = between(0.1, 0.5)  # 0.1-0.5초 대기 (매우 빠름)
    host = "http://localhost:8080"


# Locust 이벤트 핸들러
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """테스트 시작 시 초기화"""
    global oversold_count, total_purchases, failed_purchases, stock_check_failures
    oversold_count = 0
    total_purchases = 0
    failed_purchases = 0
    stock_check_failures = 0

    print("\n" + "=" * 60)
    print("🚀 Locust Load Test Started")
    print("=" * 60)
    print(f"Target: {environment.host}")
    print(
        f"Users: {environment.runner.target_user_count if hasattr(environment.runner, 'target_user_count') else 'N/A'}"
    )
    print("=" * 60 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """테스트 종료 시 결과 출력"""
    global oversold_count, total_purchases, failed_purchases, stock_check_failures

    print("\n" + "=" * 60)
    print("📊 Test Results Summary")
    print("=" * 60)
    print(f"✅ Successful Purchases: {total_purchases}")
    print(f"❌ Failed Purchases (Stock Exhausted): {failed_purchases}")
    print(f"🚨 OVERSOLD Detected: {oversold_count}")
    print(f"⚠️  Stock Mismatch Detected: {stock_check_failures}")
    print("=" * 60)

    # 초과 판매 검증 (V1 목표: 0건)
    if oversold_count > 0:
        print("❌ FAIL: Overselling detected! Stock management has bugs.")
    else:
        print("✅ PASS: No overselling detected.")

    # 재고 불일치 검증
    if stock_check_failures > 0:
        print(
            f"⚠️  WARNING: DB-Redis stock mismatch detected {stock_check_failures} times."
        )
    else:
        print("✅ PASS: DB-Redis stock consistency maintained.")

    print("=" * 60 + "\n")


@events.request.add_listener
def on_request(
    request_type, name, response_time, response_length, exception, context, **kwargs
):
    """각 요청에 대한 실시간 메트릭 수집 (선택적)"""
    # 추가 커스텀 메트릭이 필요한 경우 여기에 구현
    pass


# CLI 실행 예시 주석
"""
기본 실행 (웹 UI):
    locust -f load_tests/locustfile.py --host=http://localhost:8080

헤드리스 모드 (CLI):
    # 시나리오 1: 100명 동시 구매 테스트 (60초)
    locust -f load_tests/locustfile.py --headless --users 100 --spawn-rate 10 -t 60s --host=http://localhost:8080

    # 시나리오 2: 블랙프라이데이 (1000명, 3분)
    locust -f load_tests/locustfile.py --headless --users 1000 --spawn-rate 50 -t 3m --host=http://localhost:8080 --user-classes AggressiveBuyer

    # CSV 리포트 저장
    locust -f load_tests/locustfile.py --headless --users 100 --spawn-rate 10 -t 60s --csv=results/v1_test --host=http://localhost:8080

분산 테스트 (Master-Worker):
    # Master
    locust -f load_tests/locustfile.py --master --host=http://localhost:8080

    # Worker (여러 터미널에서)
    locust -f load_tests/locustfile.py --worker --master-host=localhost
"""
