from setuptools import setup, find_packages


runtime = set([
    "insights-core",
    "dask[bag,dataframe]",
    "distributed",
    "dask-kubernetes",
    "sklearn",
    "pandas",
])

develop = set([
    "flake8==2.6.2",
    "pytest",
])

if __name__ == "__main__":
    setup(
        name="rhat",
        version="0.0.1",
        description="Analyze a rule against insights archives.",
        author="Red Hat, Inc.",
        author_email="csams@redhat.com",
        packages=find_packages(),
        install_requires=list(runtime),
        extras_require={
            "develop": list(runtime | develop),
        },
        include_package_data=True,
    )
