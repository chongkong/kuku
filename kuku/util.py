import random
import string


alphanumeric = string.ascii_lowercase + string.digits


def random_alphanumeric(length):
    global alphanumeric
    return ''.join(random.choice(alphanumeric) for _ in range(length))


if __name__ == '__main__':
    print(random_alphanumeric(10))
