"""
V1 Stress Scenario - Locust Load Test (Black Friday)

시나리오: 300명이 100개 재고 경쟁 (3배 경쟁률!)

성능 목표:
- TPS: 100+
- 응답시간: 높은 경쟁 상황에서도 P99 < 1000ms
- 정확도: 100% (초과 판매 0건, 200명은 실패 예상)

실행 방법:
  # 웹 UI 모드
  locust -f load_tests/v1_stress/locustfile.py --host=http://localhost:8080

  # 헤드리스 모드 (300명, 2분)
  locust -f load_tests/v1_stress/locustfile.py --headless --users 300 --spawn-rate 30 -t 2m --host=http://localhost:8080
"""

import random
from typing import Dict, Optional

from locust import HttpUser, TaskSet, task, between, events


# 전역 메트릭 수집
oversold_count = 0
total_purchases = 0
failed_purchases = 0
stock_check_failures = 0


class AggressiveInventoryTaskSet(TaskSet):
    """V1 Stress 시나리오 공격적 구매자 행동 모델 (블랙프라이데이)"""

    def on_start(self):
        """각 사용자가 시작할 때 실행: 회원가입 및 로그인"""
        self.user_id = f"v1_stress_buyer_{random.randint(1, 10000000)}"
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
                "email": f"{self.user_id}@blackfriday.com",
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

    @task(2)
    def check_stock(self):
        """재고 조회 (빠른 확인)"""
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

    @task(1)
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

    @task(10)
    def purchase_product(self):
        """상품 구매 (매우 공격적 - 최우선 작업)"""
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
                # 재고 부족 (예상된 실패 - 200명은 실패해야 함)
                data = response.json()
                detail = data.get("detail", "")
                if "재고가 부족합니다" in detail or "Insufficient stock" in detail:
                    failed_purchases += 1
                    # 이것은 예상된 실패이므로 success로 처리
                    response.success()
                else:
                    response.failure(f"Purchase failed with unexpected error: {detail}")
            elif response.status_code == 404:
                # 상품을 찾을 수 없음
                response.failure(f"Product not found: {response.status_code}")
            else:
                response.failure(f"Purchase failed: {response.status_code}")


class AggressiveBuyer(HttpUser):
    """V1 Stress 시나리오 공격적 구매자 (블랙프라이데이 경쟁)"""

    tasks = [AggressiveInventoryTaskSet]
    wait_time = between(0.1, 0.5)  # 0.1-0.5초 대기 (매우 빠름!)
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
    print("⚡ V1 Stress Scenario - Black Friday Load Test Started")
    print("=" * 60)
    print(f"Target: {environment.host}")
    print(
        f"Users: {environment.runner.target_user_count if hasattr(environment.runner, 'target_user_count') else 'N/A'}"
    )
    print("Scenario: 300 aggressive buyers → 100 stock (3x competition!)")
    print("Expected: ~100 successful, ~200 failed (out of stock)")
    print("=" * 60 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """테스트 종료 시 결과 출력"""
    global oversold_count, total_purchases, failed_purchases, stock_check_failures

    print("\n" + "=" * 60)
    print("📊 V1 Stress Scenario - Black Friday Test Results")
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

    # 경쟁률 분석
    total_attempts = total_purchases + failed_purchases
    if total_attempts > 0:
        success_rate = (total_purchases / total_attempts) * 100
        print(f"\n📈 Competition Analysis:")
        print(f"   - Total purchase attempts: {total_attempts}")
        print(f"   - Success rate: {success_rate:.2f}%")
        print(f"   - Expected success rate: ~33% (100/300)")

    print("=" * 60 + "\n")
