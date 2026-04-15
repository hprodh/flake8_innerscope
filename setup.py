from setuptools import setup, find_packages

setup(
    name="flake8_innerscope",
    version="0.1.0",
    description="A flake8 plugin to enforce strict local scope usage with @innerscope decorator",
    author="hprodh",
    packages=find_packages(),
    python_requires=">=3.7",
    install_requires=["flake8 >= 3.0.0"],
    entry_points={
        'flake8.extension': [
            'INN = flake8_innerscope.innerscope:InnerScopeChecker',
        ],
    },
    classifiers=[
        "Framework :: Flake8",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
