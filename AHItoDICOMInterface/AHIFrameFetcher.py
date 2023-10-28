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
from multiprocessing.pool import ThreadPool


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
    logger = None

    def __init__(self, InstanceId , aws_access_key , aws_secret_key , AHI_endpoint = None , ahi_client = None):
        self.logger = logging.getLogger(__name__)
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
            self.logger.debug("[{__name__}]["+self.InstanceId+"] - Fetch Job added "+str(FetchJob)+".")

    def ProcessJobs(self,FetchJobs : Queue, FetchJobsCompleted : Queue , FetchJobsInError : Queue ,   aws_access_key : str = None , aws_secret_key : str = None , AHI_endpoint : str = None , ahi_client = None):  
        if ahi_client is None: 
            ahi_client = AHIClientFactory( aws_access_key= aws_access_key , aws_secret_key=aws_secret_key ,  aws_accendpoint_url=AHI_endpoint )
        while(self.thread_running):
            if not FetchJobs.empty():
                try:
                    entry = FetchJobs.get(block=False)
                    if(len(entry["frameIds"]) > 2):
                        self.logger.debug("Multiframes fetch via threadPool")
                        map_ite = []
                        i = 1
                        for frameId in entry["frameIds"]:
                            function_args = (entry["datastoreId"], entry["imagesetId"], frameId , i , ahi_client )
                            map_ite.append(function_args)
                            i = i + 1
                        with ThreadPool(100) as pool:
                            framesToOrder = []
                            results = pool.map_async(GetFramePixels, map_ite , chunksize=5 )
                            results.wait()
                        for result in results.get():
                            frame_number , pixels = result
                            framesToOrder.append({ "frame_number" : frame_number , "pixels" : pixels}) 
                        framesToOrder.sort(key=lambda x: x["frame_number"])
                        entry["PixelData"] = b''
                        for frame in framesToOrder:
                            result = frame["pixels"]
                            entry["PixelData"] = entry["PixelData"] + result
                    else:
                        self.logger.debug(f"single frame fetch for {entry['datastoreId']}/{entry['imagesetId']}/{entry['frameIds'][0]}")
                        frame_number , entry["PixelData"] = GetFramePixels( (entry["datastoreId"], entry["imagesetId"], entry["frameIds"][0] , 1 , ahi_client))
                    FetchJobsCompleted.put(entry)
                except Exception as e:
                    self.logger.error("[{__name__}]["+self.InstanceId+"] - Error while processing job "+str(entry)+" : "+str(e))
                    FetchJobsInError.put(entry)
            else:
                time.sleep(0.1)

    def getFramesFetched(self):
        if  not self.FetchJobsCompleted.empty() :
            obj = self.FetchJobsCompleted.get(block=False)
            return obj
        else:
            return None

    def Dispose(self):
        self.thread_running = False
        self.process.kill()


def GetFramePixels( val ):
    datastoreId = val[0]
    imagesetId = val[1]
    imageFrameId = val[2]
    frame_number = val[3]
    client = val[4]

    try:
        res = client.get_image_frame(
            datastoreId=datastoreId,
            imageSetId=imagesetId,
            imageFrameInformation= {'imageFrameId' : imageFrameId})
        b = io.BytesIO()
        b.write(res['imageFrameBlob'].read())
        b.seek(0)
        d = decode(b).tobytes()
        return frame_number , d
    except Exception as e:
        logging.error("[{__name__}] - Frame could not be decoded.")
        logging.error(e)
        return None