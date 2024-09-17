
from aiohttp import ClientSession
import asyncio
import base64
import json
import time

async def fetch(url, headers, session):
    async with session.get(url, headers=headers) as response:
        x = await response.json()
        y = response.status
        z = response.headers
        return [x,y,z]

async def bound_fetch(sem, url, headers, session):
    # Getter function with semaphore.
    async with sem:
        x = None
        max_retry_times = 2
        while max_retry_times >= 0:
            x = await fetch(url, headers, session)
            print(x)
            if x[1] in [404]:
                print(x[2].get('trackingId'))
                print(x[2].get('Retry-After'))
                max_retry_times -= 1
                if max_retry_times >= 0:
                    await asyncio.sleep(5)
            else:
                break
        return x

async def bound_room_fetch(sem, decodedRoomId, headers, session):
    room_str = 'ciscospark://us/ROOM/'+decodedRoomId
    roomId = base64.b64encode(room_str.encode()).decode()
    url = 'https://api.ciscospark.com/v1/rooms/{0}'.format(roomId)
    x = await bound_fetch(sem, url, headers, session)
    return [roomId, x]

async def run(roomIds):
    tasks = []
    # create instance of Semaphore
    sem = asyncio.Semaphore(1001)
    # Create client session that will ensure we dont open new connection
    # per each request.
    async with ClientSession() as session:
        start = time.time()
        for decodedRoomId in roomIds:
            # pass Semaphore and session to every GET request
            headers = {"Accept" : "application/json",
                        "Content-Type":"application/json",
                        "Authorization": "Bearer N2IyMDA0MmYtYTMzNS00NWU0LTlkODUtMTNiMDY4OTkxYWI2NDU2ZDAzZmMtZGM5_PF84_acb14e01-d869-47e4-a595-e67453279b08"}
            task = asyncio.ensure_future(bound_room_fetch(sem, decodedRoomId, headers, session))
            tasks.append(task)
        print("Completed making requests in {0} seconds.".format(time.time()-start))

        responses = asyncio.gather(*tasks)
        await responses
        print("Completed responses in {0} seconds.".format(time.time()-start))
        return responses.result()

if __name__ == "__main__":
    roomIds = ["b2bad4a0-eb5b-11e8-a170-29a9519439d5","c1aa7060-56f3-3f6a-a5ae-660d32e91dac", "c1aa7060-56f3-3f6a-a5ae-660d32e91da2", "c1aa7060-56f3-3f6a-a5ae-660d32e91dac"]
    #roomIds = ["b2bad4a0-eb5b-11e8-a170-29a9519439d6","c1aa7060-56f3-3f6a-a5ae-660d32e91dac","7dee0829-00bc-3adc-8847-4ab3de640032","d7261890-ec5a-11e8-b2ca-2f7b5de68c67","f979cb8a-37c5-37fe-a348-87719f5fced9","e9795546-bfb2-38d8-ad93-91cd6f216c21","6ac60490-057a-11e6-a0ed-c782db4f685a","4d181920-f8c9-11e8-964e-8124284c2c12","1d52b7e0-fff9-11e8-b553-5ff5b7b4d72b","78482a20-6eda-11e6-9595-6bfb5eea5dac","4a965bd0-8600-11e8-a6d5-cd80a908594f","899cf699-7300-3778-a585-55c9c3584616",
    #"46e24d80-e4d2-11e6-bc4b-69b1757bbe67","ad48b000-0ef1-11e9-92df-ef05ee3f7f0a","07899fa2-a8b7-379d-ab71-82221407726d","7c1b2fd0-dfa2-11e4-941d-253777710f89","b5358e00-5dd2-11e6-bcd7-610fe8a7350e","f0e16670-1f4c-11e9-bda6-41548dbfd095","62118910-1f4d-11e9-bda6-41548dbfd095","842ef3e0-4eef-11e8-bf2e-996c83f74f5b","56a8f530-fa8a-3f4b-8f45-ee6a17a6e48b","bb866ab0-4c85-11e8-9e02-f1f634f04a5c","4c241b90-202e-11e9-8be3-c5462bf3a7cb","de7af73f-a11e-34bb-b205-36925824e717",
    #"6deb678b-22ca-3f85-b690-1b82c102ddfb","177b1f50-257f-11e9-966c-ddc04a16f42b","93fe3290-1f2d-11e9-8846-1705f35f4201","1b1c6970-2665-11e9-a680-c759fd0da0e0","d167c799-fbd5-3836-8503-151ab2cd1f18","bc2b34ec-c2c6-3a31-94aa-cb14908b0cb0","bbc7c956-58a7-3eae-92d3-47e7bbd94350","7b3f1f82-c932-3825-946f-ae4aad44cb24","f5c33310-2fd9-11e9-bbdc-3129aa656a9e","d2fde090-9d0c-11e5-aeed-2176fdcd8a58","e59b94b0-01e4-11e8-a6b4-85bd293401c8","75a81660-8746-11e7-96b0-2feb50123d7f"]
    loop = asyncio.get_event_loop()
    future = asyncio.ensure_future(run(roomIds))
    loop.run_until_complete(future)
    for res in future.result():
        print(res)
