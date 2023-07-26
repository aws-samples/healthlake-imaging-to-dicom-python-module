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
import multiprocessing as mp




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
            self.fetcherProcessCount = int(os.cpu_count()) * 8 
        else:
            self.fetcherProcessCount = fetcher_process_count
        if dicomizer_process_count is None:
            self.DICOMizerProcessCount = int(os.cpu_count())
        else:
            self.DICOMizerProcessCount = dicomizer_process_count
        
        logging.debug(f"[AHLItoDICOM] - Fetcher process count : {self.fetcherProcessCount} , DICOMizer process count : {self.DICOMizerProcessCount}")
        #mp.set_start_method('fork')
        
    def DICOMizeByStudyInstanceUID(self, datastore_id : str = None , study_instance_uid : str = None):
        print("DICOMizebyStudyInstanceUID")
        search_criteria = {
            'filters': [
                {
                    'values': [
                        {
                            'DICOMStudyInstanceUID': study_instance_uid
                        }
                    ],
                    'operator': 'EQUAL'
                }
            ]
        }
        client = AHLIClientFactory(self.aws_access_key ,  self.aws_secret_key , self.AHLI_endpoint )
        search_result = client.search_image_sets(datastoreId=datastore_id, searchCriteria = search_criteria) ### in theory we should check if a continuation token is returned and loop until we have all the results...
        instances = []
        for imageset in search_result["imageSetsMetadataSummaries"]:
            current_imageset = imageset["imageSetId"]
            print(current_imageset)
            instances += self.DICOMizeImageSet(datastore_id=datastore_id , image_set_id=current_imageset)

        return instances

    def DICOMizeImageSet(self, datastore_id : str = None , image_set_id : str = None):
        self.ImageFrames = collections.deque()
        self.frameToDICOMize = collections.deque()
        self.DICOMizedFrames = collections.deque()
        client = AHLIClientFactory(self.aws_access_key ,  self.aws_secret_key , self.AHLI_endpoint )
        self.still_processing = True
        self.FrameDICOMizerPoolManager = Thread(target = self.AssignDICOMizeJob)
        AHLI_metadata = self.getMetadata(datastore_id, image_set_id, client) 
        if AHLI_metadata is None:
            return None
        #threads init for Frame fetching and DICOM encapsulation
        self._initFetchAndDICOMizeProcesses(AHLI_metadata=AHLI_metadata )
        series = self.getSeriesList(AHLI_metadata , image_set_id)[0]
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
                #logging.debug(f"Done {FrameFetchedCount}/{ImageFrameCount}")
                for x in range(self.fetcherProcessCount):
                    entry=self.frameFetcherThreadList[x].getFramesFetched()
                    if entry is not None:
                        FrameFetchedCount+=1
                        self.frameToDICOMize.append(entry)  
                sleep(0.01)
        logging.debug("All frames Fetched and submitted to the DICOMizer queue") 
        for x in range(self.fetcherProcessCount):
            logging.debug(f"[DICOMize] - Disposing frame fetcher thread # {x}")
            self.frameFetcherThreadList[x].Dispose()
            logging.debug(f"[DICOMize] - frame fetcher thread # {x} disposed.")
        while(self.still_processing  == True):
            logging.debug("[DICOMize] - Still processing DICOMizing...")
            sleep(0.1)

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
                    logging.debug(f"[DICOMize] - DICOMizer thread # {x} Disposed.")
                self.still_processing = False
            else:
                sleep(0.05)

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

    def getSeriesList(self, AHLI_metadata , image_set_id : str):
        ###07/25/2023 - awsjpleger :  this function is from a time when there could be multiple series withing a single ImageSetId. Still works with new AHI metadata, but should be refactored.
        seriesList = []
        for series in AHLI_metadata["Study"]["Series"]:
            SeriesNumber = AHLI_metadata["Study"]["Series"][series]["DICOM"]["SeriesNumber"] 
            Modality = AHLI_metadata["Study"]["Series"][series]["DICOM"]["Modality"] 
            try: # This is a non-mandatory tag
                SeriesDescription = AHLI_metadata["Study"]["Series"][series]["DICOM"]["SeriesDescription"]
            except:
                SeriesDescription = ""
            SeriesInstanceUID = series
            try:
                instanceCount = len(AHLI_metadata["Study"]["Series"][series]["Instances"])
            except:
                instanceCount = 0
            seriesList.append({ "ImageSetId" : image_set_id, "SeriesNumber" : SeriesNumber , "Modality" : Modality ,  "SeriesDescription" : SeriesDescription , "SeriesInstanceUID" : SeriesInstanceUID , "InstanceCount" : instanceCount})
        return seriesList

    def getMetadata(self, datastore_id, imageset_id , client = None):
        try:
            if client is None:
                client = AHLIClientFactory(self.aws_access_key ,  self.aws_secret_key , self.AHLI_endpoint )
            AHLI_study_metadata = client.get_image_set_metadata(datastoreId=datastore_id , imageSetId=imageset_id)
            json_study_metadata = gzip.decompress(AHLI_study_metadata["imageSetMetadataBlob"].read())
            json_study_metadata = json.loads(json_study_metadata)  
            return json_study_metadata
        except Exception as AHLIErr :
            logging.error(AHLIErr)
            return None
    
    def getImageSetToSeriesUIDMap(self, datastore_id : str, study_instance_uid : str ):
        search_criteria = {
            'filters': [
                {
                    'values': [
                        {
                            'DICOMStudyInstanceUID': study_instance_uid
                        }
                    ],
                    'operator': 'EQUAL'
                }
            ]
        }
        client = AHLIClientFactory(self.aws_access_key ,  self.aws_secret_key , self.AHLI_endpoint )
        search_result = client.search_image_sets(datastoreId=datastore_id, searchCriteria = search_criteria) ### in theory we should check if a continuation token is returned and loop until we have all the results...
        series_map = []
        for imageset in search_result["imageSetsMetadataSummaries"]:  
            current_imageset = imageset["imageSetId"]
            series_map.append(self.getSeriesList(self.getMetadata(datastore_id, current_imageset ) , current_imageset)[0])
        return series_map


    def getInstanceNumber(self, elem):
        return int(elem["InstanceNumber"])
    
    def getInstanceNumberInDICOM(self, elem):
        return int(elem["InstanceNumber"].value)

    def saveAsPngPIL(self, ds: Dataset , destination : str):
        try:
            folder_path = os.path.dirname(destination)
            os.makedirs( folder_path  , exist_ok=True)
            import numpy as np
            shape = ds.pixel_array.shape
            image_2d = ds.pixel_array.astype(float)
            image_2d_scaled = (np.maximum(image_2d,0) / image_2d.max()) * 255.0
            image_2d_scaled = np.uint8(image_2d_scaled)
            if 'PhotometricInterpretation' in ds and ds.PhotometricInterpretation == "MONOCHROME1":
                image_2d_scaled = np.max(image_2d_scaled) - image_2d_scaled
            img = Image.fromarray(image_2d_scaled)
            img.save(destination, 'png')
        except Exception as err:
            logging.error(f"[saveAsPngPIL] - {err}")
            return False
        return True

    # def getSeries(self, datastore_id : str = None , image_set_id : str = None):
    #     AHLI_metadata = self.getMetadata(datastore_id, image_set_id, self.AHLIclient)
    #     seriesList = self.getSeriesList(AHLI_metadata=AHLI_metadata)
    #     return seriesList  

    def _initFetchAndDICOMizeProcesses(self, AHLI_metadata):
        self.frameDICOMizerThreadList = []
        self.frameDICOMizerThreadList = []
        self.frameFetcherThreadList.clear()
        self.frameDICOMizerThreadList.clear()
        for x in range(self.fetcherProcessCount): 
            #logging.debug("[DICOMize] - Spawning AHLIFrameFetcher thread # "+str(x))
            self.frameFetcherThreadList.append(AHLIFrameFetcher(str(x), self.aws_access_key , self.aws_access_key , self.AHLI_endpoint  )) 
        for x in range(self.DICOMizerProcessCount):
            #logging.debug("[DICOMize] - Spawning AHLIDICOMizer thread # "+str(x))
            self.frameDICOMizerThreadList.append(AHLIDataDICOMizer(str(x) , AHLI_metadata )) 
    
    def saveAsDICOM(self, ds : pydicom.Dataset , destination : str = './out' ) -> bool:
        try:
            os.makedirs( destination  , exist_ok=True)
            filename = os.path.join( destination , ds["SOPInstanceUID"].value)
            ds.save_as(f"{filename}.dcm", write_like_original=False)
        except Exception as err:
            logging.error(f"[saveAsDICOM] - {err}")
            return False
        return True
