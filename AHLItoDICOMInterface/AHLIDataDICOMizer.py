"""
AHLItoDICOM Module : This class contains the logic to encapsulate the data and the pixels into a DICOM object.

SPDX-License-Identifier: Apache-2.0
"""
from time import sleep
from multiprocessing import Process , Queue
import pydicom
import logging
from pydicom.sequence import Sequence
from pydicom import Dataset , DataElement 
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import UID
import base64


class AHLIDataDICOMizer():

    ds = Dataset()
    InstanceId  = None
    thread_running = True
    AHLI_metadata = None 
    process = None

    def __init__(self, InstanceId, AHLI_metadata) -> None:
        self.InstanceId = InstanceId
        self.DICOMizeJobs = Queue()
        self.DICOMizeJobsCompleted = Queue()
        self.AHLI_metadata = AHLI_metadata
        self.process = Process(target = self.ProcessJobs , args=(self.DICOMizeJobs, self.DICOMizeJobsCompleted, ))
        self.process.start()       



    def AddDICOMizeJob(self,FetchJob):
            self.DICOMizeJobs.put(FetchJob)
            logging.debug("[AHLIFrameFetcher][AddFetchJob]["+self.InstanceId+"] - Fetch Job added "+str(FetchJob)+".")

    def ProcessJobs(self , DICOMizeJobs , DICOMizeJobsCompleted):      
        while(self.thread_running):
            if not DICOMizeJobs.empty():
                self.status="busy"
                try:
                    ImageFrame = DICOMizeJobs.get()
                    vrlist = []       
                    file_meta = FileMetaDataset()
                    self.ds = FileDataset(None, {}, file_meta=file_meta, preamble=b"\0" * 128)
                    self.getDICOMVRs(self.AHLI_metadata["Study"]["Series"][ImageFrame["SeriesUID"]]["Instances"][ImageFrame["SOPInstanceUID"]]["DICOMVRs"] , vrlist)
                    PatientLevel = self.AHLI_metadata["Patient"]["DICOM"]
                    self.getTags(PatientLevel, self.ds , vrlist)
                    StudyLevel = self.AHLI_metadata["Study"]["DICOM"]
                    self.getTags(StudyLevel, self.ds , vrlist)
                    SeriesLevel=self.AHLI_metadata["Study"]["Series"][ImageFrame["SeriesUID"]]["DICOM"]
                    self.getTags(SeriesLevel, self.ds , vrlist)
                    InstanceLevel=self.AHLI_metadata["Study"]["Series"][ImageFrame["SeriesUID"]]["Instances"][ImageFrame["SOPInstanceUID"]]["DICOM"] 
                    self.getTags(InstanceLevel ,  self.ds , vrlist)
                    self.ds.file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
                    self.ds.is_little_endian = True
                    self.ds.is_implicit_VR = False
                    file_meta.MediaStorageSOPInstanceUID = UID(ImageFrame["SOPInstanceUID"])
                    pixels = ImageFrame["PixelData"]
                    if (pixels is not None):
                        self.ds.PixelData = pixels.tobytes()
                    vrlist.clear()
                    DICOMizeJobsCompleted.put(self.ds)
                except Exception as FetchError:
                    logging.error(f"[AHLIFrameFetcher][{str(self.InstanceId)}] - {FetchError}")
            else:
                self.status = 'idle'    
                sleep(0.05)

    def getFramesDICOMized(self):
        if not self.DICOMizeJobsCompleted.empty():
            obj = self.DICOMizeJobsCompleted.get()
            return obj
        else:
            return None

    def getDataset(self):
        return self.ds

        
    def getDICOMVRs(self,taglevel, vrlist):
        for theKey in taglevel:
            vrlist.append( [ theKey , taglevel[theKey] ])
            logging.debug(f"[AHLIDataDICOMizer][getDICOMVRs] - List of private tags VRs: {vrlist}\r\n")



    def getTags(self,tagLevel, ds , vrlist):    
        for theKey in tagLevel:
            try:
                try:
                    tagvr = pydicom.datadict.dictionary_VR(theKey)
                except:  #In case the vr is not in the pydicom dictionnary, it might be a private tag , listed in the vrlist
                    tagvr = None
                    for vr in vrlist:
                        if theKey == vr[0]:
                            tagvr = vr[1]
                datavalue=tagLevel[theKey]
                #print(f"{theKey} : {datavalue}")
                if(tagvr == 'SQ'):
                    logging.debug(f"{theKey} : {tagLevel[theKey]} , {vrlist}")
                    seqs = []
                    for underSeq in tagLevel[theKey]:
                        seqds = Dataset()
                        self.getTags(underSeq, seqds, vrlist)
                        seqs.append(seqds)
                    datavalue = Sequence(seqs)
                    continue
                if(tagvr == 'US or SS'):
                    datavalue=tagLevel[theKey]
                    if (int(datavalue) > 32767):
                        tagvr = 'US'
                if( tagvr in  [ 'OB' , 'OD' , 'OF', 'OL', 'OW', 'UN' ] ):
                    base64_str = tagLevel[theKey]
                    base64_bytes = base64_str.encode('utf-8')
                    datavalue = base64.decodebytes(base64_bytes)
                if theKey == 'PrivateCreatorID': # Ignore this attribute, otherwise it creates an issue because it doesn't resolve to a DICOM tag
                    continue
                data_element = DataElement(theKey , tagvr , datavalue )
                if data_element.tag.group != 2:
                    try:
                        if (int(data_element.tag.group) % 2) == 0 : # we are skipping all the private tags
                            ds.add(data_element) 
                    except:
                        continue
            except Exception as err:
                logging.debug(f"[AHLIDataDICOMizer][getTags] - {err}")
                continue

    def Dispose(self):
        self.thread_running = False
        self.process.terminate()