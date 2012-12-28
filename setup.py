from setuptools import setup

setup(name='streamergw',
      version='0.1',
      description='Simple script to get Livestreamer and Sopcast from a central sever to the clients of a local network',
      author='Hugo',
      author_email='hugo.calleja@gmail.com',
      packages=["streamergw"],
      package_dir={ "": "src" },
      entry_points={"console_scripts": ["streamergw=streamergw.streamergw:main"]},
      requires=["livestreamer","twisted"]
      )
