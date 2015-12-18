/*
 * 1.2 Write a function void reverse(char *str) which reverses a
 * null-terminated string.
 */

#include <cmath>
#include <cstdlib>
#include <limits>
#include <array>
#include <iostream>
#include <unordered_map>
#include <string>

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wpadded"
#pragma GCC diagnostic ignored "-Wundef"
#include <benchmark/benchmark.h>
#include <gtest/gtest.h>
#pragma GCC diagnostic pop

void reverse1(char *str) {
    // First implementation. O(n) time.
    auto len = strlen(str) - 1;

    for (size_t i = 0; i <= len / 2; i++) {
        char c = str[i];
        str[i] = str[len - i];
        str[len - i] = c;
    }
}

// Unit tests

TEST(Reverse, reverse1) {
    char test1[] = "abcdefg";
    char test2[] = "abcdefg ";

    reverse1(&test1[0]);
    reverse1(&test2[0]);

    ASSERT_STREQ("gfedcba", test1);
    ASSERT_STREQ(" gfedcba", test2);
}

// Benchmarks

static unsigned int seed = 0xcec;
static const size_t lengthMin = 8;
static const size_t lengthMax = 10 << 10;

void BM_reverse1(benchmark::State& state) {
    auto len = static_cast<size_t>(state.range_x());
    auto *t = new char[len];

    for (size_t i = 0; i < len; i++)
        t[i] = rand_r(&seed) % std::numeric_limits<char>::max();

    while (state.KeepRunning()) {
        reverse1(t);
        benchmark::DoNotOptimize(t);
    }

    delete[] t;
}
BENCHMARK(BM_reverse1)->Range(lengthMin, lengthMax);

int main(int argc, char **argv) {
    // Run unit tests:
    testing::InitGoogleTest(&argc, argv);
    const auto ret = RUN_ALL_TESTS();

    // Run benchmarks:
    benchmark::Initialize(&argc, argv);
    benchmark::RunSpecifiedBenchmarks();

    return ret;
}
