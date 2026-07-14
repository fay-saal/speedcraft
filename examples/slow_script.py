def is_prime_count(n):
    count = 0
    for num in range(2, n):
        is_p = True
        for i in range(2, int(num ** 0.5) + 1):
            if num % i == 0:
                is_p = False
                break
        if is_p:
            count += 1
    return count


def fibonacci_sum(n):
    a, b = 0, 1
    total = 0
    for _ in range(n):
        total += a
        a, b = b, a + b
    return total


if __name__ == "__main__":
    print(is_prime_count(3000))
    print(fibonacci_sum(30))
