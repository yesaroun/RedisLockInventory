#!/usr/bin/env python3
"""Locust 인증 흐름 디버깅"""
import requests
import random

BASE_URL = "http://localhost:8080"

# 1. 회원가입
user_id = f"loadtest_user_{random.randint(1, 1000000)}"
print(f"1. 회원가입 시도: {user_id}")

try:
    response = requests.post(
        f"{BASE_URL}/api/auth/register",
        json={
            "username": user_id,
            "password": "test1234",
            "email": f"{user_id}@loadtest.com",
        },
    )
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.text[:200]}")
except Exception as e:
    print(f"   ❌ Exception: {e}")

# 2. 로그인
print(f"\n2. 로그인 시도")
try:
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": user_id, "password": "test1234"},
    )
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.text[:200]}")

    if response.status_code == 200:
        data = response.json()
        token = data.get("access_token")
        print(f"   ✅ 토큰 획득: {token[:30]}...")

        # 3. 상품 목록 조회
        print(f"\n3. 상품 목록 조회")
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{BASE_URL}/api/products", headers=headers)
        print(f"   Status: {response.status_code}")
        print(f"   Products: {response.json()}")

except Exception as e:
    print(f"   ❌ Exception: {e}")
    import traceback
    traceback.print_exc()
