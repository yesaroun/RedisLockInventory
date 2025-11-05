#!/bin/bash
#
# Version 1 부하 테스트 실행 스크립트
#
# 사용법:
#   ./load_tests/run_v1_tests.sh [scenario]
#
# scenario:
#   basic   - 시나리오 1: 100명 동시 구매
#   stress  - 시나리오 3: 블랙프라이데이
#   bench   - 시나리오 4: 성능 벤치마크
#   all     - 모든 시나리오 실행
#

set -e  # 에러 발생 시 중단

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 설정
HOST=${LOCUST_HOST:-http://localhost:8000}
RESULTS_DIR="results"

# 결과 디렉토리 생성
mkdir -p "$RESULTS_DIR"

# 헬스체크 함수
check_health() {
    echo -e "${BLUE}🔍 Checking server health...${NC}"
    if curl -sf "$HOST/health" > /dev/null; then
        echo -e "${GREEN}✅ Server is healthy${NC}\n"
        return 0
    else
        echo -e "${RED}❌ Server is not reachable at $HOST${NC}"
        echo -e "${YELLOW}Please start the application:${NC}"
        echo -e "  docker-compose up -d"
        return 1
    fi
}

# 시나리오 1: 기본 동시성 테스트
run_basic_test() {
    echo -e "\n${BLUE}═══════════════════════════════════════════════${NC}"
    echo -e "${BLUE}🧪 Scenario 1: Basic Concurrency Test${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════${NC}\n"

    # 테스트 데이터 초기화
    echo -e "${YELLOW}Setting up test data (100 stock)...${NC}"
    python load_tests/setup_test_data.py --scenario v1_basic --host "$HOST"

    # Locust 실행
    echo -e "\n${YELLOW}Running load test (100 users, 60 seconds)...${NC}\n"
    locust -f load_tests/locustfile.py \
        --headless \
        --users 100 \
        --spawn-rate 10 \
        --run-time 60s \
        --csv="$RESULTS_DIR/v1_basic" \
        --html="$RESULTS_DIR/v1_basic.html" \
        --host="$HOST"

    echo -e "\n${GREEN}✅ Basic test completed${NC}"
    echo -e "${BLUE}📊 Report: $RESULTS_DIR/v1_basic.html${NC}\n"
}

# 시나리오 3: 블랙프라이데이 스트레스 테스트
run_stress_test() {
    echo -e "\n${BLUE}═══════════════════════════════════════════════${NC}"
    echo -e "${BLUE}🔥 Scenario 3: Black Friday Stress Test${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════${NC}\n"

    # 테스트 데이터 초기화
    echo -e "${YELLOW}Setting up test data (100 stock, 1000 users)...${NC}"
    python load_tests/setup_test_data.py --scenario v1_stress --host "$HOST"

    # Locust 실행 (AggressiveBuyer)
    echo -e "\n${YELLOW}Running stress test (1000 users, 3 minutes)...${NC}\n"
    locust -f load_tests/locustfile.py \
        --headless \
        --users 1000 \
        --spawn-rate 50 \
        --run-time 3m \
        --user-classes AggressiveBuyer \
        --csv="$RESULTS_DIR/v1_stress" \
        --html="$RESULTS_DIR/v1_stress.html" \
        --host="$HOST"

    echo -e "\n${GREEN}✅ Stress test completed${NC}"
    echo -e "${BLUE}📊 Report: $RESULTS_DIR/v1_stress.html${NC}\n"
}

# 시나리오 4: 성능 벤치마크
run_benchmark() {
    echo -e "\n${BLUE}═══════════════════════════════════════════════${NC}"
    echo -e "${BLUE}📈 Scenario 4: Performance Benchmark${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════${NC}\n"

    # 테스트 데이터 초기화 (충분한 재고)
    echo -e "${YELLOW}Setting up test data (500 stock for sustained load)...${NC}"
    python load_tests/setup_test_data.py --scenario custom --stock 500 --host "$HOST"

    # Locust 실행 (긴 실행 시간)
    echo -e "\n${YELLOW}Running benchmark (100 users, 5 minutes)...${NC}\n"
    locust -f load_tests/locustfile.py \
        --headless \
        --users 100 \
        --spawn-rate 10 \
        --run-time 5m \
        --csv="$RESULTS_DIR/v1_benchmark" \
        --html="$RESULTS_DIR/v1_benchmark.html" \
        --host="$HOST"

    echo -e "\n${GREEN}✅ Benchmark completed${NC}"
    echo -e "${BLUE}📊 Report: $RESULTS_DIR/v1_benchmark.html${NC}\n"

    # 성능 분석
    analyze_benchmark
}

# 벤치마크 결과 분석
analyze_benchmark() {
    echo -e "\n${BLUE}═══════════════════════════════════════════════${NC}"
    echo -e "${BLUE}📊 Performance Analysis${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════${NC}\n"

    if [ -f "$RESULTS_DIR/v1_benchmark_stats.csv" ]; then
        echo -e "${YELLOW}Response Time Analysis:${NC}"
        # CSV에서 Aggregated 행 추출 (모든 요청의 통계)
        grep "Aggregated" "$RESULTS_DIR/v1_benchmark_stats.csv" | \
            awk -F',' '{
                printf "  Total Requests: %s\n", $3
                printf "  Failures: %s (%.2f%%)\n", $4, ($4/$3)*100
                printf "  Median (P50): %s ms\n", $5
                printf "  P95: %s ms\n", $8
                printf "  P99: %s ms\n", $9
                printf "  Average: %s ms\n", $6
                printf "  RPS: %.2f\n", $11
            }'

        echo -e "\n${YELLOW}V1 Goals:${NC}"
        echo -e "  Target TPS: 100"
        echo -e "  Target P50: < 100ms"
        echo -e "  Target P99: < 500ms"
        echo -e "  Target Accuracy: 100% (0 oversold)"

        echo -e "\n${BLUE}📂 Full report: $RESULTS_DIR/v1_benchmark.html${NC}\n"
    else
        echo -e "${RED}❌ Stats file not found${NC}\n"
    fi
}

# 도움말
show_help() {
    echo "Usage: $0 [scenario]"
    echo ""
    echo "Scenarios:"
    echo "  basic   - Scenario 1: 100 concurrent users (60s)"
    echo "  stress  - Scenario 3: Black Friday (1000 users, 3m)"
    echo "  bench   - Scenario 4: Performance benchmark (5m)"
    echo "  all     - Run all scenarios sequentially"
    echo ""
    echo "Environment Variables:"
    echo "  LOCUST_HOST  - Target host (default: http://localhost:8000)"
    echo ""
    echo "Examples:"
    echo "  $0 basic"
    echo "  LOCUST_HOST=http://production:8000 $0 bench"
}

# 메인 로직
main() {
    local scenario=${1:-basic}

    echo -e "${GREEN}╔═══════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                               ║${NC}"
    echo -e "${GREEN}║       Version 1 Load Testing Suite           ║${NC}"
    echo -e "${GREEN}║                                               ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════╝${NC}"
    echo -e "\n${BLUE}Target: $HOST${NC}"
    echo -e "${BLUE}Results: $RESULTS_DIR/${NC}\n"

    # 헬스체크
    if ! check_health; then
        exit 1
    fi

    # 시나리오 실행
    case $scenario in
        basic)
            run_basic_test
            ;;
        stress)
            run_stress_test
            ;;
        bench)
            run_benchmark
            ;;
        all)
            run_basic_test
            sleep 5  # 잠시 대기
            run_stress_test
            sleep 5
            run_benchmark
            ;;
        help|--help|-h)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}❌ Unknown scenario: $scenario${NC}\n"
            show_help
            exit 1
            ;;
    esac

    # 완료 메시지
    echo -e "\n${GREEN}╔═══════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                               ║${NC}"
    echo -e "${GREEN}║            All Tests Completed! 🎉            ║${NC}"
    echo -e "${GREEN}║                                               ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════╝${NC}\n"

    echo -e "${BLUE}📂 View reports in: $RESULTS_DIR/${NC}"
    echo -e "${YELLOW}Open HTML reports in your browser for detailed analysis${NC}\n"
}

# 스크립트 실행
main "$@"
