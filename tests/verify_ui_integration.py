import requests
import time
import sys

BASE_URL = "http://127.0.0.1:8000"

def test_ui_api_integration():
    print(f"Connecting to {BASE_URL}...")
    
    # 1. Test /preflight - TV Series blocking (The Office, no file, no episode)
    print("\n[Test 1] POST /preflight (TV blocking)...")
    payload = {
        "movie": "The Office",
        "quote": "That's what she said",
        "output_path": "test.wav",
        "media_type": "tv_series"
    }
    resp = requests.post(f"{BASE_URL}/preflight", json=payload)
    data = resp.json()
    print(f"Decision: {data['decision']} | Blocking: {data['blocking']}")
    assert data["decision"] == "needs_episode_scope"
    assert data["blocking"] is True
    print("Test 1: PASSED")

    # 2. Test /preflight - Mainstream warning (The Office, movie mode, no file)
    print("\n[Test 2] POST /preflight (Mainstream warning)...")
    payload["media_type"] = "movie"
    resp = requests.post(f"{BASE_URL}/preflight", json=payload)
    data = resp.json()
    print(f"Decision: {data['decision']} | Blocking: {data['blocking']}")
    assert data["decision"] == "needs_local_file"
    assert data["blocking"] is False
    print("Test 2: PASSED")

    # 3. Test /extract - Local file happy path
    print("\n[Test 3] POST /extract (Happy path)...")
    payload = {
        "movie": "Bee Movie",
        "quote": "Ya like jazz",
        "output_path": "ui_test_out.wav",
        "local_file": "C:/Users/rskrn/Desktop/agentchatrr/test_samples/test_sine.wav",
        "local_srt": "C:/Users/rskrn/Desktop/agentchatrr/test_samples/bee_movie.srt",
        "media_type": "movie"
    }
    resp = requests.post(f"{BASE_URL}/extract", json=payload)
    job_id = resp.json()["job_id"]
    print(f"Job started: {job_id}")
    
    for _ in range(15):
        resp = requests.get(f"{BASE_URL}/jobs/{job_id}")
        job = resp.json()
        print(f"Status: {job['status']} | Stage: {job.get('stage')}")
        if job["status"] == "succeeded":
            print("Job Succeeded!")
            source = job["source"]
            print(f"Source: {source['provider']} | Rights: {source['rights_status']}")
            assert source["provider"] == "local_file"
            print("Test 3: PASSED")
            return
        time.sleep(2)
    
    print("FAIL: Job timed out")

if __name__ == "__main__":
    test_ui_api_integration()
