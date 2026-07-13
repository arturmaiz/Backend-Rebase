import hashlib


class KeyNotFoundError(Exception):
    pass


class HashMapFullError(Exception):
    pass


class MyHashMap:
    MAX_SIZE = 100000
    BUCKET_COUNT = 100003

    def __init__(self, hash_function=None):
        self.bucket_count = self.BUCKET_COUNT
        self.buckets = [[] for _ in range(self.bucket_count)]
        self.size = 0

        if hash_function is None:
            self.hash_function = self.default_hash_function
        else:
            self.hash_function = hash_function

    def default_hash_function(self, key):
        key_bytes = key.encode("utf-8")
        hash_text = hashlib.md5(key_bytes).hexdigest()
        return int(hash_text, 16)

    def get_bucket_index(self, key):
        hash_number = self.hash_function(key)
        bucket_index = hash_number % self.bucket_count
        return bucket_index

    def put(self, key, value):
        bucket_index = self.get_bucket_index(key)
        bucket = self.buckets[bucket_index]

        for i, pair in enumerate(bucket):
            existing_key = pair[0]

            if existing_key == key:
                bucket[i] = (key, value)
                return

        if self.size >= self.MAX_SIZE:
            raise HashMapFullError("Hash map reached maximum size")

        bucket.append((key, value))
        self.size = self.size + 1

    def get(self, key):
        bucket_index = self.get_bucket_index(key)
        bucket = self.buckets[bucket_index]

        for pair in bucket:
            existing_key = pair[0]
            existing_value = pair[1]

            if existing_key == key:
                return existing_value

        raise KeyNotFoundError(f"Key not found: {key}")

    def remove(self, key):
        bucket_index = self.get_bucket_index(key)
        bucket = self.buckets[bucket_index]

        for i, pair in enumerate(bucket):
            existing_key = pair[0]

            if existing_key == key:
                del bucket[i]
                self.size = self.size - 1
                return
