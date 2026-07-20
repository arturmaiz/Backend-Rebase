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

    # Check only odd divisors up to the square root.
    for divisor in range(3, math.isqrt(number) + 1, 2):
        if number % divisor == 0:
            return False

    return True


def count_primes(numbers: list[int]) -> int:
    prime_count = 0

    for number in numbers:
        if is_prime(number):
            prime_count += 1

    return prime_count


def read_chunks(
    file_path: str,
    chunk_size: int,
) -> Iterator[list[int]]:
    chunk: list[int] = []

    with open(file_path, "r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()

            # Skip empty lines.
            if not line:
                continue

            try:
                number = int(line)
            except ValueError as error:
                raise ValueError(
                    f"Invalid number on line {line_number}: {line!r}"
                ) from error

            chunk.append(number)

            # Yield the chunk if it is full.
            if len(chunk) >= chunk_size:
                yield chunk
                chunk = []

    # Yield the last chunk if it is not empty.
    if chunk:
        yield chunk


def main() -> None:
    if len(sys.argv) != 2:
        print(f"🫠")
        sys.exit(1)

    file_path = sys.argv[1]
    chunk_size = 50_000

    # Use the number of CPU cores available. If not available, use 1.
    worker_count = os.cpu_count() or 1

    # Start the timer.
    start_time = time.perf_counter()

    # Use the Pool class to create a pool of workers.
    with Pool(processes=worker_count) as pool:
        # Use the imap method to process the chunks in parallel.
        results = pool.imap(
            count_primes,
            read_chunks(file_path, chunk_size),
            chunksize=1,
        )

        total_primes = sum(results)

    # Stop the timer.
    elapsed_time = time.perf_counter() - start_time

    print(f"Prime numbers: {total_primes}")
    print(f"Time: {elapsed_time:.2f} seconds")


if __name__ == "__main__":
    main()
