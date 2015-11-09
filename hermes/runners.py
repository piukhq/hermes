from django.test.runner import DiscoverRunner


class DBLessTestRunner(DiscoverRunner):
    def setup_databases(self):
        pass

    def teardown_databases(self, *args):
        pass
