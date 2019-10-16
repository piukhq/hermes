from setuptools import setup

from hermes.version import __version__

setup(
    name='hermes',
    version=__version__,
    description='Bink loyalty cards, payment cards, and users API.',
    url='https://git.bink.com/Olympus/hermes',
    author='Chris Latham',
    author_email='cl@bink.com',
    zip_safe=True)
