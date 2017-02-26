import random
import string


alphanumeric = string.ascii_lowercase + string.digits


def random_alphanumeric(length):
    global alphanumeric
    return ''.join(random.choice(alphanumeric) for _ in range(length))


class NamedObject(object):
    def __repr__(self):
        return type(self).__name__


def create_named_singleton(name):
    singleton_cls = type(name, (NamedObject,), {})
    return singleton_cls()


if __name__ == '__main__':
    print(random_alphanumeric(10))
