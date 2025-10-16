#!/usr/bin/env python3
"""
Performance Testing Script for SkillForge
Tests response times, caching, and connection pooling
"""
import requests
import time
import statistics
from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass
class PerformanceMetric:
    """Performance test result"""
    endpoint: str
    method: str
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    p95_response_time: float
    cache_hit_rate: float
    total_requests: int
    failures: int


class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    END = '\033[0m'


def print_header(text: str):
    print(f"\n{Colors.CYAN}{'='*70}{Colors.END}")
    print(f"{Colors.CYAN}{text:^70}{Colors.END}")
    print(f"{Colors.CYAN}{'='*70}{Colors.END}\n")


def print_metric(label: str, value: str, status: str = "info"):
    color = Colors.GREEN if status == "good" else Colors.YELLOW if status == "warning" else Colors.BLUE
    print(f"{color}  {label:30s} {value}{Colors.END}")


def test_endpoint(
    url: str,
    method: str = "GET",
    iterations: int = 10,
    name: str = None
) -> PerformanceMetric:
    """
    Test an endpoint's performance

    Args:
        url: The endpoint URL
        method: HTTP method
        iterations: Number of requests to make
        name: Display name for the endpoint
    """
    endpoint_name = name or url
    response_times = []
    cache_hits = 0
    failures = 0

    print(f"\n{Colors.BLUE}Testing: {endpoint_name}{Colors.END}")
    print(f"  Requests: {iterations}")

    for i in range(iterations):
        try:
            start_time = time.time()

            if method == "GET":
                response = requests.get(url, timeout=30)
            else:
                response = requests.request(method, url, timeout=30)

            elapsed = (time.time() - start_time) * 1000  # Convert to ms

            response.raise_for_status()
            response_times.append(elapsed)

            # Check cache status
            cache_status = response.headers.get('X-Cache-Status', 'MISS')
            if cache_status == 'HIT':
                cache_hits += 1

            # Progress indicator
            if (i + 1) % 5 == 0:
                print(f"  Progress: {i + 1}/{iterations} - Last: {elapsed:.2f}ms")

        except Exception as e:
            failures += 1
            print(f"{Colors.RED}  Request {i + 1} failed: {str(e)[:50]}{Colors.END}")

    # Calculate statistics
    if response_times:
        avg_time = statistics.mean(response_times)
        min_time = min(response_times)
        max_time = max(response_times)

        # Calculate 95th percentile
        sorted_times = sorted(response_times)
        p95_index = int(len(sorted_times) * 0.95)
        p95_time = sorted_times[p95_index] if sorted_times else 0

        cache_hit_rate = (cache_hits / iterations) * 100 if iterations > 0 else 0
    else:
        avg_time = min_time = max_time = p95_time = cache_hit_rate = 0

    return PerformanceMetric(
        endpoint=endpoint_name,
        method=method,
        avg_response_time=avg_time,
        min_response_time=min_time,
        max_response_time=max_time,
        p95_response_time=p95_time,
        cache_hit_rate=cache_hit_rate,
        total_requests=iterations,
        failures=failures
    )


def print_results(metrics: List[PerformanceMetric]):
    """Print performance test results"""
    print_header("PERFORMANCE TEST RESULTS")

    for metric in metrics:
        print(f"\n{Colors.CYAN}Endpoint: {metric.endpoint}{Colors.END}")
        print(f"{Colors.CYAN}{'-'*70}{Colors.END}")

        # Determine status based on response time
        if metric.avg_response_time < 100:
            status = "good"
        elif metric.avg_response_time < 500:
            status = "warning"
        else:
            status = "error"

        print_metric("Average Response Time:", f"{metric.avg_response_time:.2f}ms", status)
        print_metric("Min Response Time:", f"{metric.min_response_time:.2f}ms", "info")
        print_metric("Max Response Time:", f"{metric.max_response_time:.2f}ms", "info")
        print_metric("95th Percentile:", f"{metric.p95_response_time:.2f}ms", "info")
        print_metric("Cache Hit Rate:", f"{metric.cache_hit_rate:.1f}%", "info")
        print_metric("Total Requests:", f"{metric.total_requests}", "info")
        print_metric("Failures:", f"{metric.failures}", "error" if metric.failures > 0 else "good")


def connection_pool_test():
    """Test connection pooling efficiency"""
    print_header("CONNECTION POOLING TEST")

    # Test with session (connection pooling)
    print(f"{Colors.BLUE}Testing WITH connection pooling (requests.Session):{Colors.END}")
    session = requests.Session()
    start = time.time()

    for i in range(20):
        try:
            session.get("http://localhost/health", timeout=5)
        except Exception as e:
            print(f"{Colors.RED}Request {i+1} failed: {str(e)[:50]}{Colors.END}")

    pooled_time = time.time() - start

    # Test without session (no connection pooling)
    print(f"\n{Colors.BLUE}Testing WITHOUT connection pooling (individual requests):{Colors.END}")
    start = time.time()

    for i in range(20):
        try:
            requests.get("http://localhost/health", timeout=5)
        except Exception as e:
            print(f"{Colors.RED}Request {i+1} failed: {str(e)[:50]}{Colors.END}")

    unpooled_time = time.time() - start

    # Results
    print(f"\n{Colors.GREEN}Results:{Colors.END}")
    print_metric("WITH pooling (20 requests):", f"{pooled_time:.3f}s", "good")
    print_metric("WITHOUT pooling (20 requests):", f"{unpooled_time:.3f}s", "warning")
    improvement = ((unpooled_time - pooled_time) / unpooled_time) * 100
    print_metric("Performance improvement:", f"{improvement:.1f}%", "good" if improvement > 0 else "error")


def cache_effectiveness_test():
    """Test cache effectiveness by requesting same endpoint multiple times"""
    print_header("CACHE EFFECTIVENESS TEST")

    url = "http://localhost/game/lobby/"

    print(f"{Colors.BLUE}Making 10 requests to same endpoint to test caching:{Colors.END}")

    first_request_time = None
    subsequent_times = []

    for i in range(10):
        start = time.time()
        try:
            response = requests.get(url, timeout=10)
            elapsed = (time.time() - start) * 1000

            cache_status = response.headers.get('X-Cache-Status', 'MISS')

            if i == 0:
                first_request_time = elapsed
                print(f"  Request 1: {elapsed:.2f}ms - {cache_status} (baseline)")
            else:
                subsequent_times.append(elapsed)
                print(f"  Request {i+1}: {elapsed:.2f}ms - {cache_status}")

        except Exception as e:
            print(f"{Colors.RED}  Request {i+1} failed: {str(e)[:50]}{Colors.END}")

    if first_request_time and subsequent_times:
        avg_subsequent = statistics.mean(subsequent_times)
        improvement = ((first_request_time - avg_subsequent) / first_request_time) * 100

        print(f"\n{Colors.GREEN}Cache Analysis:{Colors.END}")
        print_metric("First request (uncached):", f"{first_request_time:.2f}ms", "info")
        print_metric("Avg subsequent requests:", f"{avg_subsequent:.2f}ms", "good")
        print_metric("Performance improvement:", f"{improvement:.1f}%", "good" if improvement > 0 else "warning")


def run_all_tests():
    """Run all performance tests"""
    print_header("SKILLFORGE PERFORMANCE TEST SUITE")

    metrics = []

    # Test various endpoints
    endpoints = [
        ("http://localhost/", "GET", "Django Homepage"),
        ("http://localhost/health", "GET", "Game Engine Health Check"),
        ("http://localhost/game/lobby/", "GET", "Game Lobby"),
    ]

    for url, method, name in endpoints:
        metric = test_endpoint(url, method=method, iterations=10, name=name)
        metrics.append(metric)
        time.sleep(0.5)  # Brief pause between endpoint tests

    # Print consolidated results
    print_results(metrics)

    # Connection pooling test
    connection_pool_test()

    # Cache effectiveness test
    cache_effectiveness_test()

    # Summary
    print_header("SUMMARY")

    avg_response_time = statistics.mean([m.avg_response_time for m in metrics])
    total_failures = sum([m.failures for m in metrics])

    print_metric("Overall Avg Response Time:", f"{avg_response_time:.2f}ms",
                 "good" if avg_response_time < 200 else "warning")
    print_metric("Total Failures:", f"{total_failures}",
                 "good" if total_failures == 0 else "error")

    if avg_response_time < 200 and total_failures == 0:
        print(f"\n{Colors.GREEN}✓ Performance tests PASSED{Colors.END}\n")
    else:
        print(f"\n{Colors.YELLOW}⚠ Performance could be improved{Colors.END}\n")


if __name__ == "__main__":
    run_all_tests()
