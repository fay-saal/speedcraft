from setuptools import setup, find_packages

setup(
    name="speedcraft-ai",
    version="0.1.0",
    description="Auto-detect and accelerate slow numeric Python functions using AI-generated Cython.",
    packages=find_packages(exclude=["tests", "examples"]),
    python_requires=">=3.9",
    install_requires=[
        "cython>=3.0",
        "anthropic>=0.30",
        "setuptools",
    ],
    entry_points={
        "console_scripts": [
            "speedcraft=speedcraft.cli:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Cython",
        "Topic :: Software Development :: Compilers",
        "Topic :: Software Development :: Code Generators",
    ],
)
