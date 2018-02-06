from setuptools import setup

setup(
    name='hermes',
    version='1.1',
    description='Bink schemes and payment cards django admin.',
    url='https://git.bink.com/Olympus/hermes',
    author='Chris Latham',
    author_email='cl@bink.com',
    packages=['django', 'admin', 'api', 'hermes', 'schemes', 'payment cards'],
    zip_safe=True)
