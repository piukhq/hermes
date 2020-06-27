class MockThreadPool:
    def __init__(self, max_workers):
        super().__init__()

    @staticmethod
    def map(*args, **kwargs):
        return map(*args, **kwargs)
