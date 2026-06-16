import httpx
import asyncio
import json

BASE_URL = "http://127.0.0.1:8005"
STEPPER_ID = "stepper_1"

async def test_health():
    print("--- Testing /health ---")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        print()

async def test_rotate():
    print(f"--- Testing /control/{STEPPER_ID}/rotate ---")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/control/{STEPPER_ID}/rotate",
            params={"value": 360, "speed": 1000, "direction": "forward"}
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        print()

async def test_steps():
    print(f"--- Testing /control/{STEPPER_ID}/steps ---")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/control/{STEPPER_ID}/steps",
            params={"value": 400, "speed": 500, "direction": "reverse"}
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        print()

async def test_stop():
    print(f"--- Testing /control/{STEPPER_ID}/stop ---")
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{BASE_URL}/control/{STEPPER_ID}/stop")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        print()

async def test_stream():
    print(f"--- Testing /process/stream/{STEPPER_ID}/set ---")
    async def event_generator():
        yield json.dumps({"type": "stream_started", "payload": {}}) + "\\n"
        await asyncio.sleep(0.5)
        yield json.dumps({"type": "partial", "payload": {"action": "rotate", "value": 90, "speed": 500, "direction": "forward"}}) + "\\n"
        await asyncio.sleep(0.5)
        yield json.dumps({"type": "completed", "payload": {}}) + "\\n"
        
    async with httpx.AsyncClient() as client:
        try:
            async with client.stream("POST", f"{BASE_URL}/process/stream/{STEPPER_ID}/set", content=event_generator()) as response:
                print(f"Status: {response.status_code}")
                async for line in response.aiter_lines():
                    if line:
                        print(f"Stream Event: {line}")
        except Exception as e:
            print(f"Stream exception: {e}")
    print()

async def main():
    await test_health()
    await test_rotate()
    await test_steps()
    await test_stop()
    await test_stream()

if __name__ == "__main__":
    asyncio.run(main())
