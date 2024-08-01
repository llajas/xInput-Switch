import asyncio
import simpleobsws
import time
import pygetwindow as gw

# Define the parameters for the WebSocket connection
parameters = simpleobsws.IdentificationParameters(ignoreNonFatalRequestChecks=False)
ws = simpleobsws.WebSocketClient(url='ws://127.0.0.1:4455', identification_parameters=parameters)

async def make_request():
    await ws.connect()
    await ws.wait_until_identified()  # Ensure the client is identified

    # Open source projector with specified geometry
    data = {
        'sourceName': 'Scene',  # Replace with your source name
        'projectorGeometry': 'AdnQywADAAAAAAAIAAAAAAAAB3cAAAQvAAAACAAAAB8AAAeHAAAEQwAAAAAABAAAB4AAAAAAAAAAAAAAB38AAAQ3'
    }
    request = simpleobsws.Request('OpenSourceProjector', data)
    result = await ws.call(request)
    print(result)

    await ws.disconnect()

time.sleep(2)  # wait two seconds to make sure OBS has been started appropriately
asyncio.run(make_request())

# Bring OBS window to the foreground
time.sleep(2)  # wait for the projector to open
obs_window = gw.getWindowsWithTitle('OBS')[0]
obs_window.activate()
