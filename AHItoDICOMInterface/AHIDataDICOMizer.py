"""
AHItoDICOM Module : This class contains the logic to encapsulate the data and the pixels into a DICOM object.

SPDX-License-Identifier: Apache-2.0
"""
from time import sleep
from multiprocessing import Process , Queue , Value , Manager
from ctypes import c_char_p
import pydicom
import logging
from pydicom.sequence import Sequence
from pydicom import Dataset , DataElement , multival
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import UID
import base64


class AHIDataDICOMizer():

    ds = Dataset()
    InstanceId  = None
    thread_running = None
    AHI_metadata = None 
    process = None
    status = None


    def __init__(self, InstanceId, AHI_metadata) -> None:
        self.InstanceId = InstanceId
        self.DICOMizeJobs = Queue()
        self.DICOMizeJobsCompleted = Queue()
        self.AHI_metadata = AHI_metadata
        manager = Manager()
        self.thread_running = manager.Value('i', 1)
        self.status = manager.Value(c_char_p, "idle")
        self.process = Process(target = self.ProcessJobs , args=(self.DICOMizeJobs, self.DICOMizeJobsCompleted, self.status , self.thread_running , self.InstanceId))
        self.process.start()




    def AddDICOMizeJob(self,FetchJob):
            self.DICOMizeJobs.put(FetchJob)
            #logging.debug("[AHIDataDICOMizer][AddDICOMizeJob]["+self.InstanceId+"] - DICOMize Job added "+str(FetchJob)+".")

    def ProcessJobs(self , DICOMizeJobs , DICOMizeJobsCompleted , status , thread_running , InstanceId):      
        while(bool(thread_running.value)):
            if not DICOMizeJobs.empty():
                status.value ="busy"
                try:
                    ImageFrame = DICOMizeJobs.get(block=False)
                    vrlist = []       
                    file_meta = FileMetaDataset()
                    self.ds = FileDataset(None, {}, file_meta=file_meta, preamble=b"\0" * 128)
                    self.getDICOMVRs(self.AHI_metadata["Study"]["Series"][ImageFrame["SeriesUID"]]["Instances"][ImageFrame["SOPInstanceUID"]]["DICOMVRs"] , vrlist)
                    PatientLevel = self.AHI_metadata["Patient"]["DICOM"]
                    self.getTags(PatientLevel, self.ds , vrlist)
                    StudyLevel = self.AHI_metadata["Study"]["DICOM"]
                    self.getTags(StudyLevel, self.ds , vrlist)
                    SeriesLevel=self.AHI_metadata["Study"]["Series"][ImageFrame["SeriesUID"]]["DICOM"]
                    self.getTags(SeriesLevel, self.ds , vrlist)
                    InstanceLevel=self.AHI_metadata["Study"]["Series"][ImageFrame["SeriesUID"]]["Instances"][ImageFrame["SOPInstanceUID"]]["DICOM"] 
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
                except Exception as DICOMizeError:
                    print("ERROR")
                    DICOMizeJobsCompleted.put(None)
                    logging.error(f"[AHIDataDICOMizer][{str(self.InstanceId)}] - {DICOMizeError}")
            else:
                status.value = 'idle'    
                sleep(0.1)
            logging.debug(f" DICOMizer Process {InstanceId} : {status.value}")
        status.value ="stopped"
        logging.debug(f" DICOMizer Process {InstanceId} : {status.value}")

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
            #logging.debug(f"[AHIDataDICOMizer][getDICOMVRs] - List of private tags VRs: {vrlist}\r\n")



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
                    #logging.debug(f"{theKey} : {tagLevel[theKey]} , {vrlist}")
                    seqs = []
                    for underSeq in tagLevel[theKey]:
                        seqds = Dataset()
                        self.getTags(underSeq, seqds, vrlist)
                        seqs.append(seqds)
                    datavalue = Sequence(seqs)
                    continue
                if(tagvr == 'US or SS'):
                    datavalue=tagLevel[theKey]
                    if isinstance(datavalue, int):  #this could be a multi value element.
                        if (int(datavalue) > 32767):
                            tagvr = 'US'
                        else:
                            tagvr = 'SS'
                    else:
                        tagvr = 'US'
                if( tagvr in  [ 'OB' , 'OD' , 'OF', 'OL', 'OW', 'UN' ] ):
                    base64_str = tagLevel[theKey]
                    base64_bytes = base64_str.encode('utf-8')
                    datavalue = base64.decodebytes(base64_bytes)
                data_element = DataElement(theKey , tagvr , datavalue )
                if data_element.tag.group != 2:
                    try:
                        ds.add(data_element) 
                    except:
                        continue
            except Exception as err:
                logging.warning(f"[AHIDataDICOMizer][getTags] - {err}")
                continue

    def Dispose(self):
        self.thread_running.value = 0
        self.process.kill()