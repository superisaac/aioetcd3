from distutils.core import setup
from setuptools import find_packages

setup(name='aioetcdm3',
      version='0.0.4',
      description='asyncio etcd3 client lib using grpclib',
      author='Zeng Ke',
      author_email='superisaac@gmail.com',
      packages=find_packages(),
      scripts=[],
      classifiers=[
          'Development Status :: 0 - Beta',
          'Environment :: Console',
          'Intended Audience :: Developers',
          'License :: MIT',
          'Programming Language :: Python :: 3.6',
          'Operating System :: POSIX',
          'Topic :: Micro-Services',
      ],
      install_requires=[
          'protobuf>=3.12.4',
          'grpclib>=0.3.2',
      ],
      python_requires='>=3.6',
)
