from setuptools import setup

setup(
    name='AHLItoDICOMInterface',
    version='0.1.0',    
    description='A package to simply export DICOM dataset in memory or on the file system.',
    url='https://github.com/shuds13/pyexample',
    author='JP Leger',
    author_email='jpleger@amazon.com',
    license='MIT-0',
    packages=['AHLItoDICOMInterface'],
    install_requires=[  'boto3',
                        'pydicom',
                        'pylibjpeg-openjpeg>=1.3.0',
                        'numpy',
                        'pillow ',                 
                      ],

    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT No Attribution License (MIT-0)',  
        'Operating System :: POSIX :: Linux',
        'Operating System :: Microsoft :: Windows',        
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10'
    ],
)