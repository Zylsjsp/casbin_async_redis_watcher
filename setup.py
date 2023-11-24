# -*- coding: utf-8 -*-
import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="casbin_async_redis_watcher",
    version="0.0.1",
    author="yangyanxing",
    author_email="yanxingyang@gmail.com",
    description="Async Casbin role watcher to be used for monitoring updates to policies for PyCasbin",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/kevinkelin/casbin_async_redis_watcher",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: Apache Software License",
    ],
    install_requires=[
        "redis>=4.2.0rc1",
        "casbin>=1.18"
    ],
    python_requires='>=3.6',
)

