from setuptools import setup

setup(
    name='MyRandR',
    version='0.1',
    py_modules=['myrandr'],
    install_requires=[
        'Click',
    ],
    entry_points='''
        [console_scripts]
        myrandr=main:main
    ''',
)
