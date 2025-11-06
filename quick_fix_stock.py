#!/usr/bin/env python3
"""재고를 Redis에 빠르게 설정하는 스크립트"""
import redis
import sqlite3

# Redis 연결
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

# SQLite 연결
conn = sqlite3.connect('inventory.db')
cursor = conn.cursor()

# 상품 추가 또는 확인
cursor.execute("SELECT id, name, stock FROM products WHERE id = 1")
product = cursor.fetchone()

if not product:
    print("상품 ID 1이 없습니다. 생성합니다...")
    cursor.execute("""
        INSERT INTO products (id, name, description, price, stock, created_at, updated_at)
        VALUES (1, 'Load Test Product', 'For testing', 10000, 100, datetime('now'), datetime('now'))
    """)
    conn.commit()
    product_id = 1
    stock = 100
    print(f"✅ 상품 ID {product_id} 생성 (재고: {stock})")
else:
    product_id, name, stock = product
    print(f"✅ 기존 상품 발견: ID {product_id}, 이름: {name}, 재고: {stock}")

# Redis에 재고 설정
r.set(f"stock:{product_id}", stock)
print(f"✅ Redis에 재고 설정: stock:{product_id} = {stock}")

# 확인
redis_stock = r.get(f"stock:{product_id}")
print(f"✅ 확인: Redis stock:{product_id} = {redis_stock}")

conn.close()
print("\n준비 완료! Locust 테스트를 실행하세요:")
print("  locust -f load_tests/locustfile.py --headless --users 100 --spawn-rate 10 --run-time 60s --host=http://localhost:8080")
