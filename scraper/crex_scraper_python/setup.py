from setuptools import setup, find_packages

setup(
    name="crex_scraper_python",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A Python scraper for cricket data from crex.live",
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/crex_scraper_python",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "Flask",
        "Flask-Cors",
        "playwright",
        "requests",
        "sqlite3"
    ],
    extras_require={
        "dev": [
            "pytest",
            "pylint",
            "black"
        ]
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)