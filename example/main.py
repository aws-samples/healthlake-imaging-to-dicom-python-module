"""
main.py : This program is an example of how to use the AHLItoDICOM module.

SPDX-License-Identifier: Apache-2.0
"""

from AHLItoDICOMInterface.AHLItoDICOM import AHLItoDICOM
import time
import os


def main():
    datastoreId = "7d997634041974df7c23aa016833ccee"
    imageSetId = "91e80f552ad9fbfa525103f3c0d368ae" #"197bc5daa72c6b7af8274fc9d180a764"
    AHLIEndpoint = "https://iad.gamma.medical-imaging.ai.aws.dev"  # Can be set to None if the default AHLI endpoint is used.

    # Default values for Frame Fetcher and DICOMizer processes count.
    # Frame Fetcher : Number of Parallelize processes to fetchand decompress the HTJ2K frames from AHLI. If Set to None the default value will be 4 x number of cores.
    # DICOMizer : Number of Parallel processes to the build the DICOM dataset form the metadata and the frames fetched. If Set to None the default value will be 1 x number of cores.
    fetcher_count = None
    dicomizer_count = None

    
    # Initialize the AHLItoDICOM conversion helper.
    helper = AHLItoDICOM( AHLI_endpoint= AHLIEndpoint , fetcher_process_count=fetcher_count , dicomizer_process_count=dicomizer_count)

    # Configure boto3 to recognize AHLI API calls.This requires to have service-2.json file in at the same folder as main.py
    # Not necessary if the environment was already configured for AHLI API via the AWS cli.
    helper.configure_boto()


    # Demonstrates how to load an ImageSet from AHLI in memory. All the instances of the ImageSet are returned in a list of pydicom dataset.
    start_time = time.time()
    instances = helper.DICOMize(datastore_id=datastoreId , image_set_id=imageSetId)
    end_time = time.time()
    print(f"{len(instances)} DICOMized in {end_time-start_time}.")
    
    # Demonstrates how to convert DICOM images to PNG representations.
    print("Exporting images of the ImageSet in png format.")
    studyUID = instances[0]["StudyInstanceUID"].value
    os.makedirs( studyUID, exist_ok=True)
    for ins in instances:
        insId = ins["SOPInstanceUID"].value
        helper.saveAsPngPIL(ds= ins, destination=f"./{studyUID}/{insId}.png")

    # Demonstrates how to save DICOM files on the filesystem.
    print("Exporting images of the ImageSet in DICOM P10 format.")
    for ins in instances:
        StudyUID = ins["StudyInstanceUID"].value
        helper.saveAsDICOM(ds= ins, destination=f"./out/{StudyUID}")

    #Demonstrates how to DICOMize a specific Series : 
    # List the series
    start_time = time.time()
    series = helper.getSeries(datastore_id=datastoreId , image_set_id=imageSetId)
    print("Series listed : ")
    print(series)
    seriesInstances = helper.DICOMize(datastore_id=datastoreId , image_set_id=imageSetId, series = series[0])
    end_time = time.time()
    print(f"Series with {len(seriesInstances)} instances DICOMized in {end_time-start_time}.")  




if __name__ == "__main__":
    main()



