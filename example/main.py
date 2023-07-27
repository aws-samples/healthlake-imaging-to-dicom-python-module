"""
main.py : This program is an example of how to use the AHItoDICOM module.

SPDX-License-Identifier: Apache-2.0
"""

from AHItoDICOMInterface.AHItoDICOM import AHItoDICOM
import time
import os
import logging

def main():
    # logging.basicConfig(level=logging.CRITICAL)
    # logging.getLogger('boto3').setLevel(logging.CRITICAL)
    # logging.getLogger('botocore').setLevel(logging.CRITICAL)
    # logging.getLogger('nose').setLevel(logging.CRITICAL)
    # logging.getLogger('urllib3').setLevel(logging.CRITICAL)
    logging.getLogger('AHItoDICOMInterface').setLevel(logging.CRITICAL)
    datastoreId = "713e4f5237a84bec991d283fa9a0788a" #Replace this value with your datastoreId.
    imageSetId = "e0b17ef98f5df1e2f01b2603c92668e0" #Replace this value with your imageSetId.
    studyInstanceUID = "1.3.6.1.4.1.19291.2.1.1.11401331443219758551361281482" #Replace this value with the studyInstanceUID of a study exisiting in the datastore.
    AHIEndpoint = None  # Can be set to None if the default AHI endpoint is used.

    # Default values for Frame Fetcher and DICOMizer processes count.
    # Frame Fetcher : Number of Parallelize processes to fetchand decompress the HTJ2K frames from AHI. If Set to None the default value will be 4 x number of cores.
    # DICOMizer : Number of Parallel processes to the build the DICOM dataset form the metadata and the frames fetched. If Set to None the default value will be 1 x number of cores.
    fetcher_count = None
    dicomizer_count = None
    
    

    # Initialize the AHItoDICOM conversion helper.
    print("Getting ImageSet JSON metadata object.")
    helper = AHItoDICOM( AHI_endpoint= AHIEndpoint , fetcher_process_count=fetcher_count , dicomizer_process_count=dicomizer_count)

    # Demonstrates how to get the metadata of an ImageSet from AHI, returned as a JSON object.
    ImageSet_metdata = helper.getMetadata(datastore_id=datastoreId , imageset_id=imageSetId)
    print(len(ImageSet_metdata))

    #Demonstrates how to get the series descriptions and ImageSetIDs by Study Instance UID
    print("Listing ImageSets and Series info by StudyInstanceUID")
    print(helper.getImageSetToSeriesUIDMap(datastore_id=datastoreId , study_instance_uid=studyInstanceUID))


    #Demonstrates how to export the DICOM study by Study Instance UID
    print("DICOMizing by StudyInstanceUID")
    instances = helper.DICOMizeByStudyInstanceUID(datastore_id=datastoreId , study_instance_uid=studyInstanceUID)

    # Demonstrates how to load an ImageSet from AHI in memory. All the instances of the ImageSet are returned in a list of pydicom dataset.
    print("DICOMizing by ImageSetID")
    start_time = time.time()
    instances = helper.DICOMizeImageSet(datastore_id=datastoreId , image_set_id=imageSetId)
    end_time = time.time()
    print(f"{len(instances)} DICOMized in {end_time-start_time}.")
    
    # # Demonstrates how to convert DICOM images to PNG representations.
    print("Exporting images of the ImageSet in png format.")
    instances = helper.DICOMizeImageSet(datastore_id=datastoreId , image_set_id=imageSetId)
    StudyUID = instances[0]["StudyInstanceUID"].value
    for ins in instances:
        insId = ins["SOPInstanceUID"].value
        helper.saveAsPngPIL(ds= ins, destination=f"./out/png_{StudyUID}/{insId}.png")

    # Demonstrates how to save DICOM files on the filesystem.
    print("Exporting images of the ImageSet in DICOM P10 format.")
    instances = helper.DICOMizeImageSet(datastore_id=datastoreId , image_set_id=imageSetId)
    for ins in instances:
        StudyUID = ins["StudyInstanceUID"].value
        helper.saveAsDICOM(ds= ins, destination=f"./out/dcm_{StudyUID}")


if __name__ == "__main__":
    main()



