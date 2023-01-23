# Amazon HealthLake Imaging DICOM Exporter module

This project is a multi-processed python 3.8+ module facilitating the load of DICOM datasets stored in Amazon HealthLake Imaging into the memory or exported to the file system .

## Getting started

This module can be installed with the python pip utility. 

1. Clone this repository:
```terminal
    git clone https://gitlab.aws.dev/wwps-hcls-sa/med-imaging/amazon-healthlake-imaging-dicom-exporter-module.git
```
2. Locate your terminal in the cloned folder.
3. Execute the below command to install the modudle via pip :
```terminal
    pip install .
```

## Configure then env to recognize the AHLI API 
At the moment this code sample is released Amazon HealthLake Imaging is still in preview release and the AWS CLI is not configured with AHLI service descriptor. Because Python Boto3 library relies on the AWS service descriptors provided by the AWS CLI, we need to add HealthLake Imaging API to the AWS CLI configuration. 

### Option 1 : Configuration with the AWS CLI
AHLI is only enabled in `us-east-1` region, make sure to set your AWS CLI to this region by default. 

Located in the `healthlakeimaging-to-dicom-exporter` cloned folder, type the following command to configure the AWS CLI with the `medical-imaging` API:
```
    aws configure add-model --service-name medical-imaging --service-model file://./service-2.json
```
When the command successfully completes the terminal is returned to its prompt with no message. The AWS CLI knows recognize the AHLI API calls, type the below command to get the help menu of AWS CLI option ofr AHLI :

```
aws medical-imaging help
```

### Option 2 : Ad hoc configuration in the python Code
This option is useful when the code using this library is executed where there is no access to the underlaying operating system ( eg. AWS Lambda ). The AHLItoDICOM helper class comes with a function called `configure_boto()`. You can call this function right after having instanciated the HLItoDICOM helper to attempt to configure the boto session. For this operation to succeed the AHLI service descriptor file `service-2.json` needs to be present at the root of your application main.


## How to use this module

To use this module you need to import the AHLItoDICOM class and instantiate the AHLItoDICOM helper:

```python
    from AHLItoDICOMInterface.AHLItoDICOM import AHLItoDICOM

    helper = AHLItoDICOM( AHLI_endpoint= AHLIEndpoint , fetcher_process_count=fetcher_count , dicomizer_process_count=dicomizer_count)
    helper.configure_boto()
```

Once the helper is instanciated, you can call th DICOMize() function to export DICOM data from AHLI into the memory, as pydicom dataset array. 

```python 
    instances = helper.DICOMize(datastore_id=datastoreId , image_set_id=imageSetId)
```

## Available functions

|Function|Description|
|--------|-----------|
AHLItoDICOM(<br>aws_access_key : str =  None,<br> aws_secret_key : str = None ,<br>AHLI_endpoint : str = None,<br> fetcher_process_count : int = None,<br> dicomizer_process_count : int = None )| Use to instantiate the helper. All paraneters are non-mandatory.<br><br> <b>aws_access_key & aws_secret_key and</b>  : Can be used if there is no default credentials configured in the aws client, or if the code runs in an environment not supporting IAM profile.<br> <b>AHLI_endpoint</b> : Only useful to AWS employees. Other users should let this value set to None.<br><b>fetcher_process_count</b> : This parameter defines the number of fetcher processes to instanciate to fetch and uncompress the frames. By default the module will create 4 x the number of cores.<br><b>dicomizer_process_count</b> : This parameter defines the number of DICOMizer processes to instanciate to create the pydicom datasets. By default the module will create 1 x the number of cores.|
| configure_boto()| This function can be used to configure the boto3 module to recognize the AHLI API calls. It requires to have the file service-2.json present int the same folder as your main application.|
|DICOMize(datastore_id : str = None,<br>image_set_id : str = None,<br>series = None)| Use to request the pydicom datasets to be loaded in memory. <br><br><b>datastore_id</b> : The AHLI datastore where the ImageSet is stored.<br><b>image_set_id</b> : The AHLI ImageSet Id of the image collection requested.<br><b>series</b> : The series object as returned by the getSeries() function , see below. If passed this parameter allows to load in memory only the pydicom datasets for this given series.|
|getSeries(datastore_id : str = None,<br>image_set_id : str = None)| Returns an array of series descriptors. Can be useful to decide whihc series to later load in memory. <br><br><b>datastore_id</b> : The AHLI datastore where the ImageSet is stored.<br><b>image_set_id</b> : The AHLI ImageSet Id of the image collection requested.<br><br>Returns an array of series descriptors like his :<br>[{'SeriesNumber': '1', 'Modality': 'CT', 'SeriesDescription': 'CT series for liver tumor from nii 014', 'SeriesInstanceUID': '1.2.826.0.1.3680043.2.1125.1.34918616334750294149839565085991567'}]|
|saveAsDICOM(ds: Dataset,<br>destination : str)| Saves the DICOM in memory object on the filesystem destination.<br><br><b>ds</b> : The pydicom dataset representing the instance. Mostly one instance of the array returned by DICOMize().<br><b>destination</b> : The file path where to store the DIOCM P10 file.|
|saveAsPngPIL(ds: Dataset,<br>destination : str)| Saves a representation of the pixel raster of one instance on the filesystem as PNG.<br><br><b>ds</b> : The pydicom dataset representing the instance. Mostly one instance of the array returned by DICOMize().<br><b>destination</b> : The file path where to store the PNG file.|

## Code Example

the file `example/main.py` demonstrates how to use the various functions described above. To use it modifiy the `datastoreId` and the `imageSetId` variables in the main function. You can also experiment by changing the `fetcher_count` and `dicomizer_count` parameters for better performance. Below is an example how the example can be started with an environment where the AWS CLI was configure with an IAM user and the region us-east-2 selected as default : 

```
$ python3 main.py
588 DICOMized in 12.933082818984985.
Exporting images of the ImageSet in png format.
Exporting images of the ImageSet in DICOM P10 format.
Series listed :
[{'SeriesNumber': '1', 'Modality': 'CT', 'SeriesDescription': 'CT series for liver tumor from nii 014', 'SeriesInstanceUID': '1.2.826.0.1.3680043.2.1125.1.34918616334750294149839565085991567'}]
Series with 588 instances DICOMized in 10.483197689056396.
```
After the example code has returned the file system now contains a folder named with the `StudyInstanceUID` of the imageSet exported within the `out` folder. This fodler holds the DICOM P10 files for the imageSet. There is also a folder named by the `StudyInstanceUId` directly at the root of this code example, this folder contains PNG representations of the DICOM images. 
```
$ ls
1.2.826.0.1.3680043.2.1125.1.19616861412188316212577695277886020  main.py  out  service-2.json
```
It is possible to pass boto3 env variables for the process using this module on the fly. The below command demonstrates how to run the example by passing the IAM credentials and the AWS region as env variables :

```
AWS_DEFAULT_REGION=us-east-1 AWS_ACCESS_KEY_ID=AKBBBBBUADXXXZTZP5EN AWS_SECRET_ACCESS_KEY=Tc9XdfGcLsY8r5edUjQpd7qasNXmYJmOB7vjg3mzU76  python3 main.py
588 DICOMized in 12.933082818984985.
Exporting images of the ImageSet in png format.
Exporting images of the ImageSet in DICOM P10 format.
Series listed :
[{'SeriesNumber': '1', 'Modality': 'CT', 'SeriesDescription': 'CT series for liver tumor from nii 014', 'SeriesInstanceUID': '1.2.826.0.1.3680043.2.1125.1.34918616334750294149839565085991567'}]
Series with 588 instances DICOMized in 10.483197689056396.
```