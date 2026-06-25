from pathlib import Path
from setuptools import setup, find_packages


def read_requirements():
    req_file = Path(__file__).parent / "requirements.txt"
    if not req_file.exists():
        return []

    return [
        line.strip()
        for line in req_file.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]


setup(
    name="dms",
    version="0.0.1",
    description="Dealer Management System for Frappe",
    author="DMS",
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=read_requirements(),
)
