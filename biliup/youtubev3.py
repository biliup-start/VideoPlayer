import json
import logging
import httplib2
import os
import random
import sys
import time

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import argparser, run_flow

from DMR.utils import uuid, replace_keywords

class youtubev3():
    # Explicitly tell the underlying HTTP transport library not to retry, since
    # we are handling retry logic ourselves.
    httplib2.RETRIES = 1
    # Maximum number of times to retry before giving up.
    MAX_RETRIES = 10
    # Always retry when these exceptions are raised.
    RETRIABLE_EXCEPTIONS = (httplib2.HttpLib2Error, IOError, ConnectionResetError)
    # Always retry when an apiclient.errors.HttpError with one of these status
    # codes is raised.
    RETRIABLE_STATUS_CODES = [500, 502, 503, 504]
    YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
    YOUTUBE_API_SERVICE_NAME = "youtube"
    YOUTUBE_API_VERSION = "v3"
    MISSING_CLIENT_SECRETS_MESSAGE = f"""
    WARNING: Please configure OAuth 2.0

    with information from the API Console
    https://console.cloud.google.com/

    For more information about the client_secrets.json file format, please visit:
    https://developers.google.com/api-client-library/python/guide/aaa_client_secrets
    """

    VALID_PRIVACY_STATUSES = ("public", "private", "unlisted")

    def __init__(
        self,
        client_secrets,
        account:str=None,
        retry_resume:int=0,
        credential_args:list=None, 
        **kwargs
    ) -> None:
        if not os.path.exists(client_secrets):
            raise FileNotFoundError(f"Client secrets file not found: {client_secrets}")
        self.client_secrets = client_secrets

        if account.endswith('.json'):
            self.account_oauth = account
        else:
            self.account_oauth = f'.login_info/{account}.json'

        self.retry_resume = retry_resume

        self.logger = logging.getLogger('DMR')
        self.auth_flags = argparser.parse_args(args=credential_args)

        self._get_authenticated_service()

    def _get_authenticated_service(self):
        storage = Storage(self.account_oauth)
        credentials = storage.get()

        if credentials is None or credentials.invalid:
            flow = flow_from_clientsecrets(self.client_secrets,
                                        scope=self.YOUTUBE_UPLOAD_SCOPE,
                                        message=self.MISSING_CLIENT_SECRETS_MESSAGE)
            credentials = run_flow(flow, storage, self.auth_flags)

        return build(self.YOUTUBE_API_SERVICE_NAME, self.YOUTUBE_API_VERSION,
                    credentials=credentials)

    def _resumable_upload(self, insert_request):
        response = None
        error = None
        retry = 0
        while response is None:
            try:
                status, response = insert_request.next_chunk()
                if 'id' in response:
                    return True, str(response['id'])
                else:
                    return False, "The upload failed with an unexpected response: %s" % response
            except HttpError as e:
                if e.resp.status in self.RETRIABLE_STATUS_CODES:
                    error = f"A retriable HTTP error {e.resp.status} occurred:\n{e.content}"
                else:
                    raise
            except self.RETRIABLE_EXCEPTIONS as e:
                error = f"A retriable error occurred: {e}"

            if error is not None:
                self.logger.error(error)
                retry += 1
                if retry > self.retry_resume:
                    return False, error

                max_sleep = min(5*retry, 60)
                sleep_seconds = random.random() * max_sleep
                self.logger.debug(f"Sleeping {sleep_seconds} seconds and then retrying...")
                time.sleep(sleep_seconds)
            else:
                retry = 0
        
        return False, 'Unknown error occurred.'
    
    def format_config(self, config, video_info=None, replace_invalid=False):
        config = config.copy()

        if config.get('raw_upload_body'):
            config['raw_upload_body'] = replace_keywords(config['raw_upload_body'], video_info, replace_invalid=replace_invalid)
            return config

        if config.get('title'):
            config['title'] = replace_keywords(config['title'], video_info, replace_invalid=replace_invalid)
            if len(config['title']) > 100:
                config['title'] = config['title'][:100]
                self.logger.warning(f'视频标题 {config["title"]} 超过100字符，已自动截取为: {config["title"]}.')
        if config.get('desc'):
            config['desc'] = replace_keywords(config['desc'], video_info, replace_invalid=replace_invalid)
        if config.get('tag'):
            config['tag'] = replace_keywords(config['tag'], video_info, replace_invalid=replace_invalid)
            
        return config

    def upload_one(self, 
        video: str,
        title: str='',
        desc: str='',
        tag: str=None,
        category: str="20",
        privacy: str="public",
        raw_upload_body: str=None,
    ):
        youtube = self._get_authenticated_service()

        if raw_upload_body:
            body = json.loads(raw_upload_body)
        else:
            tags = tag.keywords.split(",") if tag else None
            body = {
                "snippet": {
                    "title": title,
                    "description": desc,
                    "tags": tags,
                    "categoryId": str(category)
                },
                "status": {
                    "privacyStatus": privacy
                }
            }

        self.logger.debug(f"Upload config: {video}-{body}")

        insert_request = youtube.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=MediaFileUpload(video, chunksize=-1, resumable=True)
        )

        return self._resumable_upload(insert_request)

    def upload(self, files:list, **kwargs):
        if not isinstance(files, list):
            files = [files]
        
        status, message = False, ''
        for file in files:
            try:
                config = self.format_config(kwargs, file)
                sts, msg = self.upload_one(video=file, **config)
                status = status and sts
                message += msg+'\n'
            except HttpError as e:
                status= False
                message += f"An HTTP error {e.resp.status} occurred:{e.content}\n"

        return status, message.strip()
