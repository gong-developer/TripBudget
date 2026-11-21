"""Measure the configured itinerary request without printing credentials or content."""
import asyncio
import argparse
import json
import logging
from pathlib import Path
import sys
import time
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import HTTPException
from app.main import CITIES, ItineraryRequest, itinerary


async def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--server',help='Optional running API base URL')
    parser.add_argument('--output',help='Save the generated example as UTF-8 text')
    args=parser.parse_args()
    logger = logging.getLogger('app.compact_itinerary')
    logger.setLevel(logging.INFO)
    logger.addHandler(logging.StreamHandler())
    request = ItineraryRequest(cityName=CITIES[0]['cityName'], budget=1000000, days=3)
    for attempt in ('generation', 'cached'):
        started = time.monotonic()
        try:
            if args.server:
                def send():
                    body=json.dumps(request.model_dump(mode='json')).encode()
                    req=urllib.request.Request(args.server.rstrip('/')+'/api/generate-itinerary',
                        data=body,headers={'Content-Type':'application/json'})
                    with urllib.request.urlopen(req,timeout=65) as response:
                        return json.load(response)
                result=await asyncio.to_thread(send)
            else:
                result = await itinerary(request)
            if args.output and attempt=='generation':
                target=Path(args.output)
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_text(result['text'],encoding='utf-8')
            print(json.dumps({'attempt': attempt, 'seconds': round(time.monotonic()-started, 2),
                              'source': result['source'], 'complete': '3일차' in result['text']}, ensure_ascii=False), flush=True)
        except HTTPException as error:
            print(json.dumps({'attempt': attempt, 'seconds': round(time.monotonic()-started, 2),
                              'status': error.status_code, 'detail': error.detail}, ensure_ascii=False), flush=True)
            return


if __name__ == '__main__':
    asyncio.run(main())
