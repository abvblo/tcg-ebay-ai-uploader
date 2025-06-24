"""Setup script for TCG eBay Batch Uploader"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_path = Path(__file__).parent / "README.md"
long_description = readme_path.read_text() if readme_path.exists() else ""

setup(
    name="tcg-ebay-uploader",
    version="5.3.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="Automated TCG card listing tool for eBay with AI identification",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/tcg-ebay-uploader",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Games/Entertainment :: Board Games",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "aiohttp>=3.8.0",
        "aiofiles>=23.0.0",
        "diskcache>=5.6.0",
        "pandas>=2.0.0",
        "openpyxl>=3.1.0",
        "Pillow>=10.0.0",
        "tqdm>=4.65.0",
        "tenacity>=8.2.0",
        "openai>=1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "tcg-uploader=tcg_uploader.main:main",
        ],
    },
)