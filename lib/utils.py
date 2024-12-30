import aiohttp
import json
import logging
import jmespath
import jsonpath_ng.ext as jpath
from lib.config import config

# get Logger for this modul
logger = logging.getLogger(__name__)

async def get_Data_from_Url(url, token, payload=None):
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                # Check whether the request was successful
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Error: {response.status}")
                    logger.info(f"Details: {await response.text()}")
                    return None
                
    except aiohttp.ClientConnectionError as error:
        logger.error(f"Connection error: {error}")
        return None
    
async def post_data_to_Url(url, token, data):
    headers = {
        'Authorization': f'Bearer {token}',
        "Connection": "keep-alive",
        'Content-Type': 'application/json'
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=json.dumps(data), headers=headers) as response:
                # Check whether the request was successful
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Error: {response.status}")
                    logger.info(f"Details: {await response.text()}")
                    return None
                
    except aiohttp.ClientConnectionError as error:
        logger.error(f"Connection error: {error}")
        return None

async def get_Data (api_url):
     # Read URL and token from environment variables
    base_url = config.get("rcon", 0, "api_url")
    bearer_token = config.get("rcon", 0, "bearer_token")

    if not base_url:
        logger.error("API_URL environment variable is not set")
        return {'error': 'API_URL not set'}
    
    if not bearer_token:
        logger.error("BEARER_TOKEN environment variable is not set")
        return {'error': 'BEARER_TOKEN not set'}

    # Retrieve API data
    full_url = base_url + api_url
    data = await get_Data_from_Url(full_url, bearer_token)

    return data

async def post_Data(api_url, payload):
    # Read URL and token from environment variables
    base_url = config.get("rcon", 0, "api_url")
    bearer_token = config.get("rcon", 0, "bearer_token")

    if not base_url:
        logger.error("API_URL environment variable is not set")
        return {'error': 'API_URL not set'}
    
    if not bearer_token:
        logger.error("BEARER_TOKEN environment variable is not set")
        return {'error': 'BEARER_TOKEN not set'}

    # Create full URL for the API endpoint
    full_url = base_url + api_url

    # Sending the data
    response = await post_data_to_Url(full_url, bearer_token, payload)

    return response

# uses jsonpath_ng.ext and uses recrusive search
class J_Path ():
    def get_Match (path, json_string, not_match=""):
        try:
            match = jpath.parse (path).find (json_string)

            if match:
                return match[0].value
            else:
                return not_match
        except:
            logger.error ("Exception while parsing path: " + path + "in json: " + json_string)

    def get_Matches (path, json_string):
        list = []

        try:
            match = jpath.parse (path).find (json_string)

            for m in match:
                list.append (m.value)

            return list
        except:
            logger.error ("Exception while parsing path: " + path + "in json: " + json_string)

# uses jmespath and dos not support recrusive search but and and or operations
class Jmes_Path ():
    def get_Match (path, json_string, not_match=""):
        try:
            match = jmespath.search(path, json_string)

            if match:
                return match
            else:
                return not_match
            
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return not_match
