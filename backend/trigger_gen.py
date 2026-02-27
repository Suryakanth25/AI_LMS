import asyncio
import httpx
import json

async def trigger():
    data = {"subject_id": 1, "rubric_id": 1}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post("http://localhost:8000/api/generation/generate/", json=data)
            print(f"Status: {resp.status_code}")
            print(f"Response: {resp.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(trigger())
