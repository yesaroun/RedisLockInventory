#!/usr/bin/env python3
"""간단한 상품 생성 테스트 스크립트"""
import requests
import traceback

BASE_URL = "http://localhost:8080"

# 로그인
print("1. Logging in...")
login_response = requests.post(
    f"{BASE_URL}/api/auth/login",
    data={"username": "admin_loadtest", "password": "admin1234"},
)
print(f"   Status: {login_response.status_code}")

if login_response.status_code != 200:
    print(f"   Error: {login_response.text}")
    exit(1)

token = login_response.json()["access_token"]
print(f"   Token: {token[:20]}...")

# 상품 생성
print("\n2. Creating product...")
headers = {"Authorization": f"Bearer {token}"}
product_data = {
    "name": "Debug Test Product",
    "description": "Testing 500 error",
    "price": 10000,
    "stock": 100
}

try:
    response = requests.post(
        f"{BASE_URL}/api/products",
        json=product_data,
        headers=headers,
    )
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.text}")

    if response.status_code == 201:
        print("   ✅ Product created successfully!")
    else:
        print(f"   ❌ Failed with status {response.status_code}")

except Exception as e:
    print(f"   ❌ Exception: {e}")
    traceback.print_exc()
