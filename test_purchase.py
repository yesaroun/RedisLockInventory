#!/usr/bin/env python3
"""구매 API 테스트"""
import requests

BASE_URL = "http://localhost:8080"

# 1. 로그인
print("1. 로그인...")
login_response = requests.post(
    f"{BASE_URL}/api/auth/login",
    data={"username": "admin_loadtest", "password": "admin1234"},
)
token = login_response.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# 2. 상품 목록 조회
print("2. 상품 목록 조회...")
products_response = requests.get(f"{BASE_URL}/api/products", headers=headers)
print(f"   Status: {products_response.status_code}")
print(f"   Products: {products_response.json()}")

products = products_response.json()
if products:
    product_id = products[0]["id"]
    print(f"   첫 번째 상품 ID: {product_id}")

    # 3. 구매 시도
    print(f"\n3. 상품 {product_id} 구매 시도...")
    purchase_response = requests.post(
        f"{BASE_URL}/api/purchases",
        json={"product_id": product_id, "quantity": 1},
        headers=headers,
    )
    print(f"   Status: {purchase_response.status_code}")
    print(f"   Response: {purchase_response.text}")

    if purchase_response.status_code == 201:
        print("   ✅ 구매 성공!")
    else:
        print(f"   ❌ 구매 실패: {purchase_response.status_code}")
else:
    print("   ❌ 상품이 없습니다!")
