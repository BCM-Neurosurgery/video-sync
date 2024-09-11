from setuptools import setup, find_packages

setup(
    name="pyvideosync",
    version="1.1.0",
    packages=find_packages(),
    install_requires=[
        # List your project's dependencies here.
        # E.g., 'requests >= 2.19.1'
    ],
    entry_points={
        "console_scripts": [
            "plot-nev-cam-exposure=profiler.plot_nev_cam_exposure:main",
            "profile-cam-json=profiler.profile_camera_jsons:main",
            "benchmark-nevs=profiler.profile_benchmark_nevs:main",
        ],
    },
)
