import asyncio
import simpleobsws
import time
import sys

# Define OBS WebSocket parameters
parameters = simpleobsws.IdentificationParameters(ignoreNonFatalRequestChecks=False)
ws = simpleobsws.WebSocketClient(url='ws://127.0.0.1:4455', identification_parameters=parameters)

async def open_projector():
    await ws.connect()
    await ws.wait_until_identified()

    # Open projector on specific source and geometry
    data = {
        'sourceName': 'Scene',       # OBS scene source name
        'projector': 'windowed',      # 'windowed' for projector, not fullscreen plugin
        'projectorGeometry': 'AdnQywADAAAAAAAIAAAAAAAAB3cAAAQvAAAACAAAAB8AAAeHAAAEQwAAAAAABAAAB4AAAAAAAAAAAAAAB38AAAQ3'
    }
    # Use the correct request for pop-up window projector
    request = simpleobsws.Request('OpenSourceProjector', data)
    result = await ws.call(request)
    print(f"OpenSourceProjector result: {result}")
    await ws.disconnect()

if __name__ == '__main__':
    time.sleep(2)
    try:
        asyncio.run(open_projector())
    except Exception as e:
        print(f"OBS WS error: {e}")
        sys.exit(1)
    sys.exit(0)