#!/usr/bin/env python3
"""
V1 Stress 시나리오 테스트 데이터 초기화

시나리오: 블랙프라이데이 - 300명이 100개 재고 경쟁
목표: 정확히 100개만 판매, 높은 경쟁 상황에서도 정확성 보장
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
            "username": "admin_v1_stress",
            "password": "admin1234",
            "email": "admin_v1_stress@loadtest.com",
        },
    )

    if register_response.status_code not in [201, 400, 409]:  # 400, 409 = 이미 존재
        print(f"❌ Admin registration failed: {register_response.status_code}")
        print(register_response.text)
        sys.exit(1)

    # 로그인
    login_response = requests.post(
        f"{base_url}/api/auth/login",
        data={"username": "admin_v1_stress", "password": "admin1234"},
    )

    if login_response.status_code != 200:
        print(f"❌ Admin login failed: {login_response.status_code}")
        print(login_response.text)
        sys.exit(1)

    token = login_response.json()["access_token"]
    print(f"✅ Admin user created/logged in successfully")
    return token


def create_test_product(base_url: str, token: str) -> dict:
    """V1 Stress 테스트 상품 생성: 재고 100개 (블랙프라이데이 한정판)"""
    headers = {"Authorization": f"Bearer {token}"}

    product_name = "Black Friday Limited Edition"
    stock = 100

    response = requests.post(
        f"{base_url}/api/products",
        json={
            "name": product_name,
            "description": f"⚡ Black Friday Special - Only {stock} units! First come, first served!",
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
        description="Setup test data for V1 Stress scenario (Black Friday)"
    )
    parser.add_argument(
        "--host",
        default="http://localhost:8080",
        help="API server host (default: http://localhost:8080)",
    )

    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("⚡ V1 Stress Scenario - Black Friday Test Data Setup")
    print("=" * 60)
    print(f"Target: {args.host}")
    print(f"Scenario: 300 aggressive buyers → 100 stock (3x competition!)")
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
    print("Creating Black Friday limited edition product...")
    product = create_test_product(args.host, token)

    print("\n" + "=" * 60)
    print("✅ V1 Stress Test Data Setup Complete!")
    print("=" * 60)
    print(f"\n📦 Product ID: {product['id']}")
    print(f"📊 Initial Stock: {product['stock']}")
    print(f"🔥 Competition: 300 buyers fighting for {product['stock']} items!")
    print("\nYou can now run the Locust stress test:")
    print(f"  locust -f load_tests/v1_stress/locustfile.py --host={args.host}")
    print("\nOr headless mode (300 users, 2 minutes):")
    print(
        f"  locust -f load_tests/v1_stress/locustfile.py --headless --users 300 --spawn-rate 30 -t 2m --host={args.host}"
    )
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
