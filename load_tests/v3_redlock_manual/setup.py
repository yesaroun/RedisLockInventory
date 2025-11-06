#!/usr/bin/env python3
"""
V3 Redlock Manual 시나리오 테스트 데이터 초기화

시나리오: 300명이 동시에 100개 재고 상품 구매 시도 (수동 쿼럼 구현)
목표: 정확히 100개만 판매, 초과 판매 0건, 수동 Redlock 동작 검증
"""

import argparse
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import requests


def create_admin_user(base_url: str) -> str:
    """관리자 계정 생성 및 토큰 반환"""
    # 회원가입
    register_response = requests.post(
        f"{base_url}/api/auth/register",
        json={
            "username": "admin_v3_manual",
            "password": "admin1234",
            "email": "admin_v3_manual@loadtest.com",
        },
    )

    if register_response.status_code not in [201, 400, 409]:  # 400, 409 = 이미 존재
        print(f"❌ Admin registration failed: {register_response.status_code}")
        print(register_response.text)
        sys.exit(1)

    # 로그인
    login_response = requests.post(
        f"{base_url}/api/auth/login",
        data={"username": "admin_v3_manual", "password": "admin1234"},
    )

    if login_response.status_code != 200:
        print(f"❌ Admin login failed: {login_response.status_code}")
        print(login_response.text)
        sys.exit(1)

    token = login_response.json()["access_token"]
    print(f"✅ Admin user created/logged in successfully")
    return token


def create_test_product(base_url: str, token: str) -> dict:
    """V3 Redlock Manual 테스트 상품 생성: 재고 100개"""
    headers = {"Authorization": f"Bearer {token}"}

    product_name = "V3 Redlock Manual Test Product"
    stock = 100

    response = requests.post(
        f"{base_url}/api/products",
        json={
            "name": product_name,
            "description": f"V3 Redlock Manual scenario - {stock} units for 300 aggressive buyers",
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
    elif response.status_code == 409:
        # 이미 존재하는 상품 - 기존 상품 사용
        print(f"⚠️  Product '{product_name}' already exists")

        # 기존 상품 목록에서 찾기
        list_response = requests.get(
            f"{base_url}/api/products",
            headers=headers,
        )

        if list_response.status_code == 200:
            products = list_response.json()
            existing_product = next(
                (p for p in products if p["name"] == product_name), None
            )

            if existing_product:
                print(
                    f"✅ Using existing product: {existing_product['name']} (ID: {existing_product['id']}, Stock: {existing_product['stock']})"
                )
                return existing_product

        print(f"❌ Failed to find existing product")
        sys.exit(1)
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
    parser = argparse.ArgumentParser(
        description="Setup test data for V3 Redlock Manual scenario"
    )
    parser.add_argument(
        "--host",
        default="http://localhost:8080",
        help="API server host (default: http://localhost:8080)",
    )

    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("V3 Redlock Manual Scenario - Test Data Setup")
    print("=" * 60)
    print(f"Target: {args.host}")
    print(f"Scenario: 300 aggressive buyers → 100 stock")
    print(f"Redlock: Manual quorum implementation (5 Redis nodes, quorum 3/5)")
    print("=" * 60 + "\n")

    # 헬스체크
    print("Checking server health...")
    if not check_health(args.host):
        print(f"❌ Server is not reachable at {args.host}")
        sys.exit(1)
    print("✅ Server is healthy\n")

    # 관리자 계정 생성
    print("Creating admin user...")
    token = create_admin_user(args.host)
    print()

    # 테스트 상품 생성
    print("Creating test product...")
    product = create_test_product(args.host, token)

    print("\n" + "=" * 60)
    print("✅ V3 Redlock Manual Test Data Setup Complete!")
    print("=" * 60)
    print(f"\n📦 Product ID: {product['id']}")
    print(f"📊 Initial Stock: {product['stock']}")
    print(f"\n🔒 Distributed Lock: Manual quorum implementation")
    print(f"📡 Redis Nodes: 5 (quorum 3/5)")
    print("\nYou can now run the Locust test:")
    print(f"  locust -f load_tests/v3_redlock_manual/locustfile.py --host={args.host}")
    print("\nOr headless mode:")
    print(
        f"  locust -f load_tests/v3_redlock_manual/locustfile.py --headless --users 300 --spawn-rate 10 -t 60s --host={args.host}"
    )
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
