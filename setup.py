from setuptools import setup

setup(
    name='AHItoDICOMInterface',
    version='0.1.3',    
    description='A package to simply export DICOM data from AWS HealthImaging in your application memory or the file system.',
    url='https://github.com/aws-samples/healthlake-imaging-to-dicom-python-module',
    long_description='More details about the project and features can be found on the project\'s GitHub page.',
    author='JP Leger',
    author_email='jpleger@amazon.com',
    license='MIT-0',
    packages=['AHItoDICOMInterface'],
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
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11'
    ],
            
)