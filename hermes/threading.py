from concurrent.futures.thread import ThreadPoolExecutor
from functools import wraps

from django.db import connection


# Referenced from
# https://stackoverflow.com/questions/57211476/django-orm-leaks-connections-when-using-threadpoolexecutor
class DjangoThreadPoolExecutor(ThreadPoolExecutor):
    """
    When a function is passed into the ThreadPoolExecutor via either submit() or map(),
    this will wrap the function, and make sure that close_django_db_connection() is called
    inside the thread when it's finished so Django doesn't leak DB connections.

    Since map() calls submit(), only submit() needs to be overwritten.
    """
    def close_django_db_connection(self):
        connection.close()

    def generate_thread_closing_wrapper(self, fn):
        @wraps(fn)
        def new_func(*args, **kwargs):
            try:
                res = fn(*args, **kwargs)
            except Exception as e:
                self.close_django_db_connection()
                raise e
            else:
                self.close_django_db_connection()
                return res
        return new_func

    def submit(*args, **kwargs):
        """
        args filtering/unpacking logic from

        https://github.com/python/cpython/blob/3.7/Lib/concurrent/futures/thread.py

        """
        if len(args) >= 2:
            self, fn, *args = args
            fn = self.generate_thread_closing_wrapper(fn=fn)
        elif not args:
            raise TypeError("descriptor 'submit' of 'ThreadPoolExecutor' object "
                            "needs an argument")
        elif 'fn' in kwargs:
            self, *args = args
            fn = self.generate_thread_closing_wrapper(fn=kwargs.pop('fn'))

        return super(self.__class__, self).submit(fn, *args, **kwargs)
