"""
AHItoDICOM Module : This class contains the logic to query the Image pixel raster.

SPDX-License-Identifier: Apache-2.0
"""
from multiprocessing import Process , Queue
import logging
from openjpeg import decode
import io
from .AHIClientFactory import * 
import time


class AHIFrameFetcher:

    
    status = 'idle'
    FetchJobs = None
    FetchJobsCompleted = None
    FetchJobsInError = None
    InstanceId= None
    client = None
    thread_running = True
    process = None
    aws_access_key = None
    aws_secret_key = None
    AHI_endpoint = None

    def __init__(self, InstanceId , aws_access_key , aws_secret_key , AHI_endpoint = None , ahi_client = None):
        self.InstanceId = InstanceId
        self.FetchJobs = Queue()
        self.FetchJobsCompleted = Queue()
        self.FetchJobsInError = Queue()
        self.aws_secret_key = aws_access_key
        self.aws_secret_key = aws_secret_key
        self.AHI_endpoint = AHI_endpoint
        self.ahi_client = ahi_client
        self.process = Process(target = self.ProcessJobs , args=(self.FetchJobs,self.FetchJobsCompleted, self.FetchJobsInError ,  self.aws_access_key , self.aws_secret_key , self.AHI_endpoint , self.ahi_client))
        self.process.start()
   
    def AddFetchJob(self,FetchJob):
            self.FetchJobs.put(FetchJob)
            #print(f"[FrameFetcher][{self.InstanceId}] Job entry added")
            #print(FetchJob)
            #logging.debug("[AHIFrameFetcher][AddFetchJob]["+self.InstanceId+"] - Fetch Job added "+str(FetchJob)+".")

    def ProcessJobs(self,FetchJobs : Queue, FetchJobsCompleted : Queue , FetchJobsInError : Queue ,   aws_access_key : str = None , aws_secret_key : str = None , AHI_endpoint : str = None , ahi_client = None):  
        if ahi_client is None: 
            ahi_client = AHIClientFactory( aws_access_key= aws_access_key , aws_secret_key=aws_secret_key ,  aws_accendpoint_url=AHI_endpoint )
        while(self.thread_running):
            if not FetchJobs.empty():
                try:
                    entry = FetchJobs.get(block=False)
                    entry["PixelData"] = self.curieGetFramePixels(entry["datastoreId"], entry["studyId"], entry["frameId"] , ahi_client)
                    FetchJobsCompleted.put(entry)
                except:
                    FetchJobsInError.put(entry)
            else:
                time.sleep(0.1)

            

    def getFramesFetched(self):
        if  not self.FetchJobsCompleted.empty() :
            obj = self.FetchJobsCompleted.get(block=False)
            return obj
        else:
            return None


    def curieGetFramePixels(self, datastoreId, studyId, imageFrameId , client ):
        try:

            res = client.get_image_frame(
                datastoreId=datastoreId,
                imageSetId=studyId,
                imageFrameInformation= {'imageFrameId' :imageFrameId})
            b = io.BytesIO()
            b.write(res['imageFrameBlob'].read())
            b.seek(0)
            d = decode(b)
            return d
        except Exception as e:
            logging.error("[AHIFramefetcher] - Frame could not be decoded.")
            logging.error(e)
            return None
    
    def Dispose(self):
        self.thread_running = False
        self.process.kill()