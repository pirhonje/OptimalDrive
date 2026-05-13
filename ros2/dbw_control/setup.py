from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'dbw_control'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='henry',
    maintainer_email='henry@example.fi',
    description='TODO: Package description',
    license='TODO: License declaration',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
        'dbw_steering_validate = dbw_control.steering_validate:main',
        'dbw_throttle_validate = dbw_control.throttle_validate:main',
    	],
    },
)
