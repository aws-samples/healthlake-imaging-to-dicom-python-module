"""
AHLItoDICOM Module : This class contains the logic to create the AHLI boto3 client.

SPDX-License-Identifier: Apache-2.0
"""
import boto3
import tempfile
import logging



class AHLIClientFactory(object):


    def __init__(self) -> None:
        pass

    def __new__(self , aws_access_key : str = None , aws_secret_key : str = None , aws_accendpoint_url : str = None):
        try:
            session = boto3.Session()
            session._loader.search_paths.extend([tempfile.gettempdir()])
            AHLIclient = boto3.client('medical-imaging',  aws_access_key_id = aws_access_key , aws_secret_access_key = aws_secret_key ,  endpoint_url=aws_accendpoint_url  ) 
            return AHLIclient
        except Exception as AHLIErr:
            logging.error(f"[AHLIClientFactory] - {AHLIErr}")
            return None