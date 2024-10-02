"""
AHItoDICOM Module : This class contains the logic to encapsulate the data and the pixels into a DICOM object.

SPDX-License-Identifier: Apache-2.0
"""
import base64
import logging

import pydicom.uid
import pydicom.datadict
from pydicom import Dataset, DataElement
from pydicom.sequence import Sequence
from pydicom.dataset import FileDataset, FileMetaDataset


class AHIDataDICOMizer():

    def __init__(self, ahi_metadata) -> None:
        self.logger = logging.getLogger(__name__)
        self.ahi_metadata = ahi_metadata

    def dicomize(self, frames) -> list[FileDataset]:
        # self.logger.info(f"DICOMizing {len(frames)} framesets")
        dicoms = []

        try:
            vrlist = []
            ds = FileDataset(
                None, {}, file_meta=FileMetaDataset(), preamble=b"\0" * 128)
            self.get_dicom_vrs(self.ahi_metadata["Study"]["Series"][frames["SeriesUID"]]
                                ["Instances"][frames["SOPInstanceUID"]]["DICOMVRs"], vrlist)
            patient_level = self.ahi_metadata["Patient"]["DICOM"]
            self.populate_tags(patient_level, ds, vrlist)
            study_level = self.ahi_metadata["Study"]["DICOM"]
            self.populate_tags(study_level, ds, vrlist)
            series_level = self.ahi_metadata["Study"]["Series"][frames["SeriesUID"]]["DICOM"]
            self.populate_tags(series_level, ds, vrlist)
            instance_level = self.ahi_metadata["Study"]["Series"][frames["SeriesUID"]]["Instances"][frames["SOPInstanceUID"]]["DICOM"]
            self.populate_tags(instance_level,  ds, vrlist)
            ds.file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
            ds.is_little_endian = True
            ds.is_implicit_VR = False
            ds.file_meta.MediaStorageSOPInstanceUID = pydicom.uid.UID(frames["SOPInstanceUID"])

            if frames["PixelData"]:
                ds.PixelData = frames["PixelData"]

            dicoms.append(ds)
        except Exception:
            self.logger.exception(f"Error dicomizing {frames = }")

        return dicoms

    def get_dicom_vrs(self, tag_level, vrlist) -> None:
        for key in tag_level:
            vrlist.append([key, tag_level[key]])
            self.logger.debug(f"[{__name__}][getDICOMVRs] - List of private tags VRs: {vrlist}")

    def populate_tags(self, tag_level, ds, vrlist) -> None:
        for key in tag_level:
            try:
                try:
                    tagvr = pydicom.datadict.dictionary_VR(key)
                except:
                    # In case the vr is not in the pydicom dictionnary, it might be a private tag, listed in the vrlist
                    tagvr = None

                    for vr in vrlist:
                        if key == vr[0]:
                            tagvr = vr[1]

                datavalue = tag_level[key]

                if tagvr == "SQ":
                    seqs = []
                    for under_seq in tag_level[key]:
                        seqds = Dataset()
                        self.populate_tags(under_seq, seqds, vrlist)
                        seqs.append(seqds)
                    datavalue = Sequence(seqs)

                if tagvr == "US or SS":
                    datavalue = tag_level[key]

                    # this could be a multi value element.
                    if isinstance(datavalue, int):
                        if int(datavalue) > 32767:
                            tagvr = "US"
                        else:
                            tagvr = "SS"
                    else:
                        tagvr = "US"

                if tagvr in ["OB", "OD", "OF", "OL", "OW", "UN", "OB or OW"]:
                    base64_str = tag_level[key]
                    base64_bytes = base64_str.encode("utf-8")
                    datavalue = base64.decodebytes(base64_bytes)

                data_element = DataElement(key, tagvr, datavalue)

                if data_element.tag.group != 2:
                    try:
                        ds.add(data_element)
                    except:
                        continue

            except Exception as ex:
                # self.logger.warning(f"get_tags failed with {ex}: {key = }")
                continue
