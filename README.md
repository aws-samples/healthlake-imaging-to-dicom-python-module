# Amazon HealthLake Imaging DICOM Exporter module

This project is a multi-processed python 3.8+ module facilitating the load of DICOM datasets stored in Amazon HealthLake Imaging into the memory or exported to the file system .

## Getting started

This module can be installed with the python pip utility. 

1. Clone this repository:
```terminal
    git clone https://github.com/aws-samples/healthlake-imaging-to-dicom-python-module.git
```
2. Locate your terminal in the cloned folder.
3. Execute the below command to install the modudle via pip :
```terminal
    pip install .
```

## How to use this module

To use this module you need to import the AHItoDICOM class and instantiate the AHItoDICOM helper:

```python
    from AHItoDICOMInterface.AHItoDICOM import AHItoDICOM

    helper = AHItoDICOM( AHI_endpoint= AHIEndpoint , fetcher_process_count=fetcher_count , dicomizer_process_count=dicomizer_count)
```

Once the helper is instanciated, you can call th DICOMize() function to export DICOM data from AHI into the memory, as pydicom dataset array. 

```python 
    instances = helper.DICOMizeImageSet(datastore_id=datastoreId , image_set_id=imageSetId)
```

## Available functions

|Function|Description|
|--------|-----------|
AHItoDICOM(<br>aws_access_key : str =  None,<br> aws_secret_key : str = None ,<br>AHI_endpoint : str = None,<br> fetcher_process_count : int = None,<br> dicomizer_process_count : int = None )| Use to instantiate the helper. All paraneters are non-mandatory.<br><br> <b>aws_access_key & aws_secret_key and</b>  : Can be used if there is no default credentials configured in the aws client, or if the code runs in an environment not supporting IAM profile.<br> <b>AHI_endpoint</b> : Only useful to AWS employees. Other users should let this value set to None.<br><b>fetcher_process_count</b> : This parameter defines the number of fetcher processes to instanciate to fetch and uncompress the frames. By default the module will create 4 x the number of cores.<br><b>dicomizer_process_count</b> : This parameter defines the number of DICOMizer processes to instanciate to create the pydicom datasets. By default the module will create 1 x the number of cores.|
|DICOMizeImageSet(datastore_id: str, image_set_id: str)| Use to request the pydicom datasets to be loaded in memory. <br><br><b>datastore_id</b> : The AHI datastore where the ImageSet is stored.<br><b>image_set_id</b> : The AHI ImageSet Id of the image collection requested.<br>|
|DICOMizeByStudyInstanceUID(datastore_id: str, study_instance_uid: str)| Use to request the pydicom datasets to be loaded in memory. <br><br><b>datastore_id</b> : The AHI datastore where the ImageSet is stored.<br><b>study_instance_uid</b> : The DICOM study instance uid of the Study to export.<br>|
|getImageSetToSeriesUIDMap(datastore_id: str, study_instance_uid: str)| Returns an array of thes series descriptors for the given study, associated with theit ImageSetIds. Can be useful to decide which series to later load in memory. <br><br><b>datastore_id</b> : The AHI datastore where the ImageSet is stored.<br><b>study_instance_uid</b> : The study instance UID of the DICOM study.<br><br>Returns an array of series descriptors like his :<br>[{'SeriesNumber': '1', 'Modality': 'CT', 'SeriesDescription': 'CT series for liver tumor from nii 014', 'SeriesInstanceUID': '1.2.826.0.1.3680043.2.1125.1.34918616334750294149839565085991567'}]|
|saveAsDICOM(ds: Dataset,<br>destination : str)| Saves the DICOM in memory object on the filesystem destination.<br><br><b>ds</b> : The pydicom dataset representing the instance. Mostly one instance of the array returned by DICOMize().<br><b>destination</b> : The file path where to store the DIOCM P10 file.|
|saveAsPngPIL(ds: Dataset,<br>destination : str)| Saves a representation of the pixel raster of one instance on the filesystem as PNG.<br><br><b>ds</b> : The pydicom dataset representing the instance. Mostly one instance of the array returned by DICOMize().<br><b>destination</b> : The file path where to store the PNG file.|

## Code Example

The file `example/main.py` demonstrates how to use the various functions described above. To use it modifiy the `datastoreId`  the `imageSetId` and the `studyInstanceUID` variables in the main function. You can also experiment by changing the `fetcher_count` and `dicomizer_count` parameters for better performance. Below is an example how the example can be started with an environment where the AWS CLI was configure with an IAM user and the region us-east-2 selected as default : 

```
$ python3 main.py
python main.py 
Getting ImageSet JSON metadata object.
5
Listing ImageSets and Series info by StudyInstanceUID
[{'ImageSetId': '0aaf9a3b6405bd6d393876806034b1c0', 'SeriesNumber': '3', 'Modality': 'CT', 'SeriesDescription': 'KneeHR  1.0  B60s', 'SeriesInstanceUID': '1.3.6.1.4.1.19291.2.1.2.1140133144321975855136128320349', 'InstanceCount': 74}, {'ImageSetId': '81bfc6aa3416912056e95188ab74870b', 'SeriesNumber': '2', 'Modality': 'CT', 'SeriesDescription': 'KneeHR  3.0  B60s', 'SeriesInstanceUID': '1.3.6.1.4.1.19291.2.1.2.1140133144321975855136128221126', 'InstanceCount': 222}]
DICOMizing by StudyInstanceUID
DICOMizebyStudyInstanceUID
0aaf9a3b6405bd6d393876806034b1c0
81bfc6aa3416912056e95188ab74870b
DICOMizing by ImageSetID
222 DICOMized in 3.3336379528045654.
Exporting images of the ImageSet in png format.
Exporting images of the ImageSet in DICOM P10 format.
```
After the example code has returned the file system now contains folders named with the `StudyInstanceUID` of the imageSet exported within the `out` folder. This fodler prefixed with `dcm_` holds the DICOM P10 files for the imageSet. The folder prefixed with `png_` holds PNG image representations of the imageSet. 
```
