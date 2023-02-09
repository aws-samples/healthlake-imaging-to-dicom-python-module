"""
AHLItoDICOM Module : This class contains the logic to query the Image pixel raster.

SPDX-License-Identifier: Apache-2.0
"""

from .AHLIDataDICOMizer import *
from .AHLIFrameFetcher import *
from .AHLIClientFactory import * 
import json
import logging
import collections
from threading import Thread
from time import sleep
from PIL import Image
import gzip
import tempfile
import os
import shutil

logging.basicConfig( level="INFO" )

class AHLItoDICOM:

    AHLIclient = None
    frameFetcherThreadList = []
    frameDICOMizerThreadList = []
    fetcherProcessCount = None
    DICOMizerProcessCount = None
    ImageFrames = None
    frameToDICOMize = None
    FrameDICOMizerPoolManager = None
    DICOMizedFrames = None
    CountToDICOMize = 0
    still_processing = False
    aws_access_key = None
    aws_secret_key = None
    AHLI_endpoint = None

    def __init__(self, aws_access_key : str =  None, aws_secret_key : str = None , AHLI_endpoint : str = None , fetcher_process_count : int = None , dicomizer_process_count : int = None ) -> None:
        self.ImageFrames = collections.deque()
        self.frameToDICOMize = collections.deque()
        self.DICOMizedFrames = collections.deque()
        self.aws_access_key = aws_access_key
        self.aws_secret_key =  aws_secret_key
        self.AHLI_endpoint = AHLI_endpoint
        if fetcher_process_count is None:
            self.fetcherProcessCount = int(os.cpu_count()) * 4 
        else:
            self.fetcherProcessCount = fetcher_process_count
        if dicomizer_process_count is None:
            self.DICOMizerProcessCount = int(os.cpu_count())
        else:
            self.DICOMizerProcessCount = dicomizer_process_count
        
        logging.debug(f"[AHLItoDICOM] - Fetcher process count : {self.fetcherProcessCount} , DICOMizer process count : {self.DICOMizerProcessCount}")
        

    def DICOMize(self, datastore_id : str = None , image_set_id : str = None , series = None ):
        self.AHLIclient = AHLIClientFactory(self.aws_access_key ,  self.aws_secret_key , self.AHLI_endpoint )
        self.still_processing = True
        self.FrameDICOMizerPoolManager = Thread(target = self.AssignDICOMizeJob)
        AHLI_metadata = self.AHLIGetMetadata(datastore_id, image_set_id, self.AHLIclient) 
        if AHLI_metadata is None:
            return None
        #threads init for Frame fetching and DICOM encapsulation
        self._initFetchAndDICOMizeProcesses(AHLI_metadata=AHLI_metadata )
        seriesList = self.getSeriesList(AHLI_metadata)
        if series is None:
            for series in seriesList:
                self.ImageFrames.extendleft(self.getImageFrames(datastore_id, image_set_id , AHLI_metadata , series["SeriesInstanceUID"])) 
        else:
            self.ImageFrames.extendleft(self.getImageFrames(datastore_id, image_set_id , AHLI_metadata , series["SeriesInstanceUID"])) 
        ImageFrameCount = len(self.ImageFrames) 
        logging.debug(f"[DICOMize] - Importing {ImageFrameCount} instances in memory.")
        self.CountToDICOMize = ImageFrameCount
        self.FrameDICOMizerPoolManager.start()
        
        #Assigning jobs to the Frame fetching thread pool.
        threadId = 0
        while(len(self.ImageFrames)> 0):
            self.frameFetcherThreadList[threadId].AddFetchJob(self.ImageFrames.popleft())
            threadId+=1
            if threadId == self.fetcherProcessCount :
                threadId = 0  
        FrameFetchedCount = 0
        while(FrameFetchedCount < (ImageFrameCount)):
                logging.debug(f"Done {FrameFetchedCount}/{ImageFrameCount}")
                for x in range(self.fetcherProcessCount):
                    entry=self.frameFetcherThreadList[x].getFramesFetched()
                    if entry is not None:
                        FrameFetchedCount+=1
                        self.frameToDICOMize.append(entry)  
        logging.debug("All frames Fetched and submitted to the DICOMizer queue") 
        for x in range(self.fetcherProcessCount):
            logging.debug(f"[DICOMize] - Disposing frame fetcher thread # {x}")
            self.frameFetcherThreadList[x].Dispose()
        while(self.still_processing  == True):
            logging.debug("[DICOMize] - Still processing DICOMizing...")
            sleep(0.05)

        returnlist = list(self.DICOMizedFrames)
        returnlist.sort( key= self.getInstanceNumberInDICOM)
        return returnlist




    def AssignDICOMizeJob(self):
        #this function rounds robin accross all the dicomizer threads, until all the images are actually dicomized.
        logging.debug(f"[AssignDICOMizeJob] - DICOMizer Thread Assigner started.")
        keep_running = True
        while( keep_running):
            while( len(self.frameToDICOMize) > 0):
                threadId = 0
                self.frameDICOMizerThreadList[threadId].AddDICOMizeJob(self.frameToDICOMize.popleft())
                threadId+=1 
                if(threadId == self.DICOMizerProcessCount):
                    threadId = 0
            for x in range(self.DICOMizerProcessCount):
                while( not self.frameDICOMizerThreadList[x].DICOMizeJobsCompleted.empty()):
                    self.DICOMizedFrames.append(self.frameDICOMizerThreadList[x].getFramesDICOMized())
            dc = len(self.DICOMizedFrames)
            #print(dc)

            if(len(self.DICOMizedFrames)  == self.CountToDICOMize):
                keep_running = False
                logging.debug(f"DICOMized count : {dc}")
                for x in range(self.DICOMizerProcessCount):
                    logging.debug(f"[DICOMize] - Disposing DICOMizer thread # {x}")
                    self.frameDICOMizerThreadList[x].Dispose()
                self.still_processing = False
            else:
                sleep(0.1)

        logging.debug(f"[AssignDICOMizeJob] - DICOMizer Thread Assigner finished.")        

    def getImageFrames(self, datastoreId, studyId , AHLI_metadata , seriesUid) -> collections.deque:
        instancesList = []
        for instances in AHLI_metadata["Study"]["Series"][seriesUid]["Instances"]:
            if len(AHLI_metadata["Study"]["Series"][seriesUid]["Instances"][instances]["ImageFrames"]) < 1:
                print("Skipping the following instances because they do not contain ImageFrames: " + instances)
                continue
            try:        
                frameId = AHLI_metadata["Study"]["Series"][seriesUid]["Instances"][instances]["ImageFrames"][0]["ID"]
                InstanceNumber = AHLI_metadata["Study"]["Series"][seriesUid]["Instances"][instances]["DICOM"]["InstanceNumber"]
                instancesList.append( { "datastoreId" : datastoreId, "studyId" : studyId , "frameId" : frameId , "SeriesUID" : seriesUid , "SOPInstanceUID" : instances,  "InstanceNumber" : InstanceNumber , "PixelData" : None})
            except Exception as e: # The code above failes for 
                print(e)
        instancesList.sort(key=self.getInstanceNumber)
        return collections.deque(instancesList)

    def getSeriesList(self, AHLI_metadata):
        seriesList = []
        for series in AHLI_metadata["Study"]["Series"]:
            SeriesNumber = AHLI_metadata["Study"]["Series"][series]["DICOM"]["SeriesNumber"] 
            Modality = AHLI_metadata["Study"]["Series"][series]["DICOM"]["Modality"] 
            try: # This is a non-mandatory tag
                SeriesDescription = AHLI_metadata["Study"]["Series"][series]["DICOM"]["SeriesDescription"]
            except:
                SeriesDescription = ""
            SeriesInstanceUID = series
            seriesList.append({ "SeriesNumber" : SeriesNumber , "Modality" : Modality ,  "SeriesDescription" : SeriesDescription , "SeriesInstanceUID" : SeriesInstanceUID})
        return seriesList

    def AHLIGetMetadata(self, datastoreId, studyId , client):
        try:
            AHLI_study_metadata = client.get_image_set_metadata(datastoreId=datastoreId , imageSetId=studyId)
            json_study_metadata = gzip.decompress(AHLI_study_metadata["imageSetMetadataBlob"].read())
            json_study_metadata = json.loads(json_study_metadata)  
            return json_study_metadata
        except Exception as AHLIErr :
            logging.error(AHLIErr)
            return None

    def getInstanceNumber(self, elem):
        return int(elem["InstanceNumber"])
    
    def getInstanceNumberInDICOM(self, elem):
        return int(elem["InstanceNumber"].value)

    def saveAsPngPIL(self, ds: Dataset , destination : str):
        import numpy as np
        shape = ds.pixel_array.shape
        image_2d = ds.pixel_array.astype(float)
        image_2d_scaled = (np.maximum(image_2d,0) / image_2d.max()) * 255.0
        image_2d_scaled = np.uint8(image_2d_scaled)
        if 'PhotometricInterpretation' in ds and ds.PhotometricInterpretation == "MONOCHROME1":
            image_2d_scaled = np.max(image_2d_scaled) - image_2d_scaled
        img = Image.fromarray(image_2d_scaled)
        
        img.save(destination, 'png')


    def getSeries(self, datastore_id : str = None , image_set_id : str = None):
        AHLI_metadata = self.AHLIGetMetadata(datastore_id, image_set_id, self.AHLIclient)
        seriesList = self.getSeriesList(AHLI_metadata=AHLI_metadata)
        return seriesList  

    def _initFetchAndDICOMizeProcesses(self, AHLI_metadata , ):
        self.frameFetcherThreadList.clear()
        self.frameDICOMizerThreadList.clear()
        for x in range(self.fetcherProcessCount): 
            logging.debug("[DICOMize] - Spawning AHLIFrameFetcher thread # "+str(x))
            self.frameFetcherThreadList.append(AHLIFrameFetcher(str(x), self.aws_access_key , self.aws_access_key , self.AHLI_endpoint )) 
        for x in range(self.DICOMizerProcessCount):
            logging.debug("[DICOMize] - Spawning AHLIDICOMizer thread # "+str(x))
            self.frameDICOMizerThreadList.append(AHLIDataDICOMizer(str(x) , AHLI_metadata ))
        
    def configure_boto(self):
        os.environ['AWS_DATA_PATH'] = tempfile.gettempdir()
        serviceModelPath = os.path.join(tempfile.gettempdir(), 'medical-imaging/2022-10-19')
        os.makedirs(serviceModelPath, exist_ok=True)
        try:
            shutil.copyfile('service-2.json', os.path.join(serviceModelPath, 'service-2.json'))
        except Exception as err:
            logging.error(f"[AHLIClientFactory] - {err}")
    
    def saveAsDICOM(self, ds : pydicom.Dataset , destination : str = './out' ) -> bool:
        try:
            os.makedirs( destination  , exist_ok=True)
            filename = os.path.join( destination , ds["SOPInstanceUID"].value)
            ds.save_as(f"{filename}.dcm", write_like_original=False)
        except Exception as err:
            logging.error(f"[saveAsDICOM] - {err}")
            return False
        return True
