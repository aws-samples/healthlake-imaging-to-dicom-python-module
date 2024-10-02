"""
AHItoDICOM Module : This class contains the logic to query the Image pixel raster.

SPDX-License-Identifier: Apache-2.0
"""

import os
import gzip
import json
import logging
import collections

import boto3
from PIL import Image
from .AHIDataDICOMizer import *
from .AHIFrameFetcher import *


class AHItoDICOM:

    AHIclient = None
    frameFetcherThreadList = []
    frameDICOMizerThreadList = []
    FrameDICOMizerPoolManager = None
    CountToDICOMize = 0
    still_processing = False

    def __init__(self) -> None:
        """
        Helper class constructor.

        :param aws_access_key: Optional IAM user access key.
        :param aws_secret_key: Optional IAM user secret key.
        :param AHI_endpoint: Optional AHI endpoint URL. Only useful to AWS employees.
        :param fetcher_process_count: Optional number of processes to use for fetching frames. Will default to CPU count x 8
        :param dicomizer_process_count: Optional number of processes to use for DICOMizing frames.Will default to CPU count.
        """
        self.logger = logging.getLogger(__name__)
        self.image_frames = collections.deque()

    def dicomize_imageset(self, datastore_id: str, imageset_id: str) -> list[pydicom.FileDataset]:
        """
        Single-threaded DICOMizer for use in AWS Lambda Functions
        """

        client = boto3.client("medical-imaging")
        ahi_metadata = self.get_metadata(datastore_id, imageset_id, client)

        if ahi_metadata is None:
            self.logger.error(
                f"[{__name__}] - No metadata found for {datastore_id = }, {imageset_id = }")

            return None

        ahi_frame_fetcher = AHIFrameFetcher(client)
        ahi_data_dicomizer = AHIDataDICOMizer(ahi_metadata)
        series = self.get_series_list(ahi_metadata, imageset_id)[0]
        self.image_frames.extendleft(self.get_image_frames(
            datastore_id, imageset_id, ahi_metadata, series["SeriesInstanceUID"]))
        instanceCount = len(self.image_frames)
        self.CountToDICOMize = instanceCount
        dicoms = []

        while (len(self.image_frames) > 0):
            frames = ahi_frame_fetcher.fetch(self.image_frames.popleft())
            dicoms += ahi_data_dicomizer.dicomize(frames)

        # Sort dicoms by instance number
        dicoms.sort(key=lambda x: int(x["InstanceNumber"].value))

        return dicoms

    def get_image_frames(self, datastore_id, imageset_id, ahi_metadata, series_uid) -> collections.deque:
        instances = []

        for instance_id, data in ahi_metadata["Study"]["Series"][series_uid]["Instances"].items():
            if len(data["ImageFrames"]) < 1:
                self.logger.info(f"Skipping instance because it do not contain ImageFrames: {instance_id}")
                continue
            try:
                frame_ids = [f["ID"] for f in data["ImageFrames"]]
                instance_number = data["DICOM"]["InstanceNumber"]
                instances.append({
                    "datastoreId": datastore_id,
                    "imagesetId": imageset_id,
                    "frameIds": frame_ids,
                    "SeriesUID": series_uid,
                    "SOPInstanceUID": instance_id,
                    "InstanceNumber": instance_number,
                    "PixelData": None
                })

            except Exception:
                self.logger.exception(f"[{__name__}]")

        instances.sort(key=lambda x: int(x["InstanceNumber"]))

        return collections.deque(instances)

    def get_series_list(self, ahi_metadata, image_set_id: str) -> list[dict]:
        # 07/25/2023 - awsjpleger :  this function is from a time when there could be multiple series withing a single ImageSetId. Still works with new AHI metadata, but should be refactored.
        seriesList = []
        for series in ahi_metadata["Study"]["Series"]:
            SeriesNumber = ahi_metadata["Study"]["Series"][series]["DICOM"]["SeriesNumber"]
            Modality = ahi_metadata["Study"]["Series"][series]["DICOM"]["Modality"]
            try:  # This is a non-mandatory tag
                series_description = ahi_metadata["Study"]["Series"][series]["DICOM"]["SeriesDescription"]
            except:
                series_description = ""
            series_instance_uid = series
            try:
                instanceCount = len(
                    ahi_metadata["Study"]["Series"][series]["Instances"])
            except:
                instanceCount = 0
            seriesList.append({"ImageSetId": image_set_id, "SeriesNumber": SeriesNumber, "Modality": Modality,
                              "SeriesDescription": series_description, "SeriesInstanceUID": series_instance_uid, "InstanceCount": instanceCount})
        return seriesList

    def get_metadata(self, datastore_id, imageset_id, client):
        """
        getMetadata(datastore_id : str = None , image_set_id : str  , client : str = None).

        :param datastore_id: The datastoreId containtaining the DICOM Study.
        :param image_set_id: The ImageSetID of the data to be DICOMized from AHI.
        :param client: Optional boto3 medical-imaging client. The functions creates its own client by default.
        :return: a JSON structure corresponding to the ImageSet Metadata.
        """
        try:
            AHI_study_metadata = client.get_image_set_metadata(
                datastoreId=datastore_id, imageSetId=imageset_id)
            json_study_metadata = gzip.decompress(
                AHI_study_metadata["imageSetMetadataBlob"].read())
            json_study_metadata = json.loads(json_study_metadata)
            return json_study_metadata
        except Exception as AHIErr:
            self.logger.error(f"[{__name__}] - {AHIErr}")
            return None

    def saveAsPngPIL(self, ds: Dataset, destination: str):
        """
        saveAsPngPIL(ds : pydicom.Dataset , destination : str).
        Saves a PNG representation of the DICOM object to the specified destination.

        :param ds: The pydicom Dataset representing the DICOM object.
        :param destination: the file path where the file needs to be dumped to. the file path must include the file name and extension.
        """
        try:
            folder_path = os.path.dirname(destination)
            os.makedirs(folder_path, exist_ok=True)
            import numpy as np
            shape = ds.pixel_array.shape
            image_2d = ds.pixel_array.astype(float)
            image_2d_scaled = (np.maximum(image_2d, 0) /
                               image_2d.max()) * 255.0
            image_2d_scaled = np.uint8(image_2d_scaled)
            if 'PhotometricInterpretation' in ds and ds.PhotometricInterpretation == "MONOCHROME1":
                image_2d_scaled = np.max(image_2d_scaled) - image_2d_scaled
            img = Image.fromarray(image_2d_scaled)
            img.save(destination, 'png')
        except Exception as err:
            self.logger.error(f"[{__name__}][saveAsPngPIL] - {err}")
            return False
        return True

    def save_as_dicom(self, ds: pydicom.Dataset, destination: str) -> str:
        """
        saveAsDICOM(ds : pydicom.Dataset , destination : str).
        Saves a DICOM Part10 file for the DICOM object to the specified destination.

        :param ds: The pydicom Dataset representing the DICOM object.
        :param destination: the folder path where to save the DICOM file to. The file name will be the SOPInstanceUID of the DICOM object suffixed by '.dcm'.
        """

        filename = f"{os.path.join(destination, ds['SOPInstanceUID'].value)}.dcm"

        try:
            os.makedirs(destination, exist_ok=True)
            ds.save_as(filename, write_like_original=False)

        except Exception as err:
            self.logger.exception(f"[{__name__}][saveAsDICOM] - {err}")

        return filename
