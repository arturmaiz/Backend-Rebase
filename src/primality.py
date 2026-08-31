"""Large-scale primality test (lesson 1).

Reads a text file with one integer per line, counts primes using all CPU cores,
and prints the total plus elapsed time.
"""

import math
import os
import sys
import time
from collections.abc import Iterator
from multiprocessing import Pool


def is_prime(number: int) -> bool:
    if number < 2:
        return False
    if number == 2:
        return True
    if number % 2 == 0:
        return False

    for divisor in range(3, math.isqrt(number) + 1, 2):
        if number % divisor == 0:
            return False

    return True


def count_primes(numbers: list[int]) -> int:
    return sum(1 for number in numbers if is_prime(number))


def read_chunks(file_path: str, chunk_size: int) -> Iterator[list[int]]:
    chunk: list[int] = []

    with open(file_path, encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                number = int(line)
            except ValueError as error:
                raise ValueError(
                    f"Invalid number on line {line_number}: {line!r}"
                ) from error

            chunk.append(number)
            if len(chunk) >= chunk_size:
                yield chunk
                chunk = []

    if chunk:
        yield chunk


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python primality.py <input-file>", file=sys.stderr)
        sys.exit(1)

    file_path = sys.argv[1]
    chunk_size = 50_000
    worker_count = os.cpu_count() or 1

    start_time = time.perf_counter()

    with Pool(processes=worker_count) as pool:
        results = pool.imap(
            count_primes,
            read_chunks(file_path, chunk_size),
            chunksize=1,
        )
        total_primes = sum(results)

    elapsed_time = time.perf_counter() - start_time

    print(f"Prime numbers: {total_primes}")
    print(f"Time: {elapsed_time:.2f} seconds")


if __name__ == "__main__":
    main()
