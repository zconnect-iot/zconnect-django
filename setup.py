#!/usr/bin/env python

from setuptools import setup


TESTS_REQUIRE = [
    "pytest",
    "pytest-flakes",
    "pytest-cov",
    "pytest-xdist",
    "pytest-django",
    "tavern>=0.7.6",
    "factory_boy",
    "freezegun",
    "colorlog",
    "mockredispy",
    "testfixtures",
]


SETUP_REQUIRES = [
    "setuptools>=36",
    "pytest-runner",
]


if __name__ == "__main__":
    setup(
        name="zconnect",
        setup_requires=SETUP_REQUIRES,
        tests_require=TESTS_REQUIRE,
        extras_require={
            "tests": TESTS_REQUIRE,
            "sampling": [
                "gevent==1.2.2",
                "psycogreen",
            ]
        }
    )
