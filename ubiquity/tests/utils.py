

class MockThreadPool:
    def __init__(self, max_workers):
        super().__init__()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    @staticmethod
    def map(*args, **kwargs):
        return map(*args, **kwargs)
