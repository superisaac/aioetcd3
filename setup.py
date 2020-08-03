from distutils.core import setup
from setuptools import find_packages

setup(name='aioetcd3',
      version='0.0.1',
      description='asyncio etcd3 client lib using grpclib',
      author='Zeng Ke',
      author_email='zk@bixin.com',
      packages=find_packages(),
      scripts=[],
      classifiers=[
          'Development Status :: 4 - Beta',
          'Environment :: Console',
          'Intended Audience :: Developers',
          'License :: MIT',
          'Programming Language :: Python :: 3.6',
          'Operating System :: POSIX',
          'Topic :: Micro-Services',
      ],
      install_requires=[
          'protobuf',
          'grpclib',
      ],
      python_requires='>=3.6',
)
