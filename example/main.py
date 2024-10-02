"""
main.py : This program is an example of how to use the AHItoDICOM module.

SPDX-License-Identifier: Apache-2.0
"""

from AHItoDICOMInterface.AHItoDICOM import AHItoDICOM
import time
import logging

def main():
    logging.getLogger('AHItoDICOMInterface').setLevel(logging.DEBUG)
    logging.getLogger('AHItoDICOMInterface.AHIFrameFetcher').setLevel(logging.DEBUG)
    datastore_id = "" # Replace this value with your datastoreId.
    imageset_id = "" # Replace this value with your imageSetId.

    # Initialize the AHItoDICOM conversion helper.
    helper = AHItoDICOM()
    start_time = time.time()
    instances = helper.dicomize_imageset(datastore_id=datastore_id, imageset_id=imageset_id)
    end_time = time.time()

    print(f"{len(instances)} DICOMized in {end_time-start_time}.")
    print("Exporting images of the ImageSet in DICOM P10 format.")

    for instance in instances:
        study_uid = instance["StudyInstanceUID"].value
        helper.save_as_dicom(ds=instance, destination=f"./out/dcm_{study_uid}")


if __name__ == "__main__":
    main()
