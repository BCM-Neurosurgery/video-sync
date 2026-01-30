from setuptools import setup, find_packages

setup(
    name="pyvideosync",
    version="1.2.0",
    packages=find_packages(),
    install_requires=[
        # List your project's dependencies here.
        # E.g., 'requests >= 2.19.1'
    ],
    entry_points={
        "console_scripts": [
            "stitch-videos=pyvideosync.main:cli",
            "plot-nev-cam-exposure=profiler.plot_nev_cam_exposure:main",
            "profile-cam-json=profiler.profile_camera_jsons:main",
            "benchmark-nevs=profiler.benchmark_nevs:main",
            "benchmark-camera=profiler.benchmark_camera_files:main",
            "plot-nev-agg-discontinuity=profiler.plot_nev_agg_discontinuity:main",
            "plot-json-agg-discontinuity=profiler.plot_json_agg_discontinuity:main",
        ],
    },
)
