#!/usr/bin/env python3
"""
테스트 데이터 초기화 스크립트

부하 테스트 실행 전 테스트 상품 및 재고를 설정합니다.
"""

import argparse
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import requests


def create_admin_user(base_url: str) -> str:
    """관리자 계정 생성 및 토큰 반환"""
    # 회원가입
    register_response = requests.post(
        f"{base_url}/api/auth/register",
        json={
            "username": "admin_loadtest",
            "password": "admin1234",
            "email": "admin@loadtest.com",
        },
    )

    if register_response.status_code not in [201, 400, 409]:  # 400, 409 = 이미 존재
        print(f"❌ Admin registration failed: {register_response.status_code}")
        print(register_response.text)
        sys.exit(1)

    # 로그인
    login_response = requests.post(
        f"{base_url}/api/auth/login",
        data={"username": "admin_loadtest", "password": "admin1234"},
    )

    if login_response.status_code != 200:
        print(f"❌ Admin login failed: {login_response.status_code}")
        print(login_response.text)
        sys.exit(1)

    token = login_response.json()["access_token"]
    print(f"✅ Admin user created/logged in successfully")
    return token


def create_test_product(base_url: str, token: str, name: str, stock: int) -> dict:
    """테스트 상품 생성"""
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.post(
        f"{base_url}/api/products",
        json={
            "name": name,
            "description": f"Load test product - {stock} units available",
            "price": 10000,
            "stock": stock,
        },
        headers=headers,
    )

    if response.status_code == 201:
        product = response.json()
        print(
            f"✅ Product created: {product['name']} (ID: {product['id']}, Stock: {stock})"
        )
        return product
    else:
        print(f"❌ Product creation failed: {response.status_code}")
        print(response.text)
        sys.exit(1)


def check_health(base_url: str) -> bool:
    """서버 헬스체크"""
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def main():
    parser = argparse.ArgumentParser(description="Setup test data for load testing")
    parser.add_argument(
        "--host",
        default="http://localhost:8080",
        help="API server host (default: http://localhost:8080)",
    )
    parser.add_argument(
        "--scenario",
        choices=["v1_basic", "v1_stress", "custom"],
        default="v1_basic",
        help="Test scenario preset",
    )
    parser.add_argument(
        "--stock",
        type=int,
        default=100,
        help="Initial stock for custom scenario (default: 100)",
    )

    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("Load Test Data Setup")
    print("=" * 60)
    print(f"Target: {args.host}")
    print(f"Scenario: {args.scenario}")
    print("=" * 60 + "\n")

    # 헬스체크
    print("Checking server health...")
    if not check_health(args.host):
        print(f"Server is not reachable at {args.host}")
        sys.exit(1)
    print("Server is healthy\n")

    # 2. 관리자 계정 생성
    print("Creating admin user...")
    token = create_admin_user(args.host)
    print()

    # 3. 시나리오별 상품 생성
    print("Creating test products...")

    if args.scenario == "v1_basic":
        # 시나리오 1: 재고 100개 상품 생성 (Locust에서 100명 가상 사용자가 구매 시도)
        create_test_product(args.host, token, "V1 Basic Test Product", 100)

    elif args.scenario == "v1_stress":
        # 블랙프라이데이: 재고 100개 상품 생성 (Locust에서 1000명 가상 사용자가 경쟁)
        create_test_product(args.host, token, "Black Friday Limited Edition", 100)

    elif args.scenario == "custom":
        # 커스텀 시나리오: 원하는 재고 수량으로 상품 생성
        create_test_product(args.host, token, f"Custom Test Product", args.stock)

    print("\n" + "=" * 60)
    print("✅ Test Data Setup Complete!")
    print("=" * 60)
    print("\nYou can now run Locust tests:")
    print(f"  locust -f load_tests/locustfile.py --host={args.host}")
    print("\nOr headless mode:")
    print(
        f"  locust -f load_tests/locustfile.py --headless --users 100 --spawn-rate 10 -t 60s --host={args.host}"
    )
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
