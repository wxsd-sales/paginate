import requests
import asyncio
from concurrent.futures import ThreadPoolExecutor

def fetch(session, url, headers):
    with session.get(url, headers=headers) as response:
        try:
            data = response.json()
        except Exception as e:
            data = response.text
        return [data, response.status_code, response.headers]

def bound_fetch(session, url, token):
    headers =  {"Accept" : "application/json",
                "Content-Type":"application/json",
                "Authorization": "Bearer {0}".format(token)}
    max_retry_times = 2
    while max_retry_times >= 0:
        result = fetch(session, url, headers)
        if result[1] in [429, 502, 503, 599]:
            if result[1] == 429:
                retry_after = result[2].get('Retry-After')
                if retry_after == None:
                    retry_after = 20
            else:
                print(url)
                max_retry_times -= 1
                retry_after = 5
            print("{0} hit, waiting for {1} seconds and then retrying...".format(result[1], retry_after))
            if max_retry_times >= 0:
                #await asyncio.sleep(int(retry_after))
                time.sleep(int(retry_after))
        else:
            break
    return result

def bound_room_fetch(session, roomId, token):
    url = 'https://api.ciscospark.com/v1/rooms/{0}'.format(roomId)
    room = bound_fetch(session, url, token)
    room.insert(0, roomId)
    #print(room)
    return room


async def get_rooms_asynchronous(rooms, token):
    #print("{0:<30} {1:>20}".format("File", "Completed at"))
    headers =  {"Accept" : "application/json",
                "Content-Type":"application/json",
                "Authorization": "Bearer {0}".format(token)}
    with ThreadPoolExecutor(max_workers=10) as executor:
        with requests.Session() as session:
            # Set any session parameters here before calling `fetch`
            loop = asyncio.get_event_loop()
            tasks = [
                loop.run_in_executor(executor,bound_room_fetch, *(session, room[0], token)) # Allows us to pass in multiple arguments to `fetch`
                for room in rooms
            ]
            #for response in await asyncio.gather(*tasks):
            #    pass
            responses = asyncio.gather(*tasks)
            await responses
            return responses.result()

def main():
    rooms = [["Y2lzY29zcGFyazovL3VzL1JPT00vMmY5MTliZWUtYTY3Yi0zOTk0LTg1ZjktOTg4ZDhhOTVlMzQ5", "ABCDEFGH"],
             ["Y2lzY29zcGFyazovL3VzL1JPT00vMmY5MTRlNDEtYjU4OC0zYzZmLTgxMjItNjc0ZTNlYjNmZDli", "ABCDEFGH"],
             ["Y2lzY29zcGFyazovL3VzL1JPT00vMmY5MzRjOWQtZWRhYS0zZDRjLWI2YjMtOGUwN2YyMDRlYjI0", "ABCDEFGH"],
             ["Y2lzY29zcGFyazovL3VzL1JPT00vMmY5NTFhOWQtODJjNS0zYTEwLWJlNjYtZDQxMmE0ZmNkNjcz", "ABCDEFGH"],
             ["Y2lzY29zcGFyazovL3VzL1JPT00vM2E1YmNlYzAtZGIzZS0xMWU3LTk1NTItNGI2ZWI1MGIzMTQ4", "ABCDEFGH"]]
    token = "OWRlNWM4NTctZDkwMy00YTM5LTgxMDItZWI3OTI3MzkxNTRiZmE1ZDRlOGQtMTJi_PF84_602d7d50-4ed5-40fc-a8ad-63646501cd00"
    loop = asyncio.get_event_loop()
    future = asyncio.ensure_future(get_rooms_asynchronous(rooms, token))
    loop.run_until_complete(future)
    print(future.result())

main()
