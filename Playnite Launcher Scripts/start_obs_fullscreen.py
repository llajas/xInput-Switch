import argparse
import asyncio
import sys

import simpleobsws


DEFAULT_GEOMETRY = "AdnQywADAAAAAAAIAAAAAAAAB3cAAAQvAAAACAAAAB8AAAeHAAAEQwAAAAAABAAAB4AAAAAAAAAAAAAAB38AAAQ3"


def request_succeeded(result) -> bool:
    if hasattr(result, "ok") and callable(getattr(result, "ok")):
        return bool(result.ok())

    request_status = getattr(result, "requestStatus", None)
    if request_status is not None:
        return bool(getattr(request_status, "result", False))

    # Fallback for library versions that do not expose status cleanly.
    return True


async def open_projector(args) -> int:
    url = f"ws://{args.host}:{args.port}"

    for attempt in range(1, args.attempts + 1):
        parameters = simpleobsws.IdentificationParameters(
            ignoreNonFatalRequestChecks=False,
            eventSubscriptions=0,
        )
        ws = simpleobsws.WebSocketClient(
            url=url,
            password=args.password,
            identification_parameters=parameters,
        )

        try:
            await ws.connect()
            await ws.wait_until_identified()

            data = {
                "sourceName": args.source,
                "projector": "windowed",
                "projectorGeometry": args.geometry,
            }
            result = await ws.call(simpleobsws.Request("OpenSourceProjector", data))
            if request_succeeded(result):
                print(f"PROJECTOR_OPENED attempt={attempt} source={args.source}")
                return 0

            print(f"PROJECTOR_REQUEST_FAILED attempt={attempt} result={result}")
        except Exception as exc:
            print(f"OBS_WS_ERROR attempt={attempt} error={exc}")
        finally:
            try:
                await ws.disconnect()
            except Exception:
                pass

        if attempt < args.attempts:
            await asyncio.sleep(args.retry_delay)

    return 1


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4455)
    parser.add_argument("--password", default="")
    parser.add_argument("--source", default="Scene")
    parser.add_argument("--geometry", default=DEFAULT_GEOMETRY)
    parser.add_argument("--attempts", type=int, default=8)
    parser.add_argument("--retry-delay", type=float, default=0.75)
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    try:
        sys.exit(asyncio.run(open_projector(arguments)))
    except Exception as exc:
        print(f"PROJECTOR_FATAL error={exc}")
        sys.exit(1)
