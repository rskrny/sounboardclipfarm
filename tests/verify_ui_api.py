import requests
import time
import sys

BASE_URL = "http://127.0.0.1:8000"

def test_ui_flow():
    print(f"Connecting to {BASE_URL}...")
    
    # 1. Start extraction
    payload = {
        "movie": "Bee Movie",
        "quote": "Ya like jazz",
        "output_path": "ui_test_out.wav",
        "local_file": "C:/Users/rskrn/Desktop/agentchatrr/test_samples/test_sine.wav",
        "local_srt": "C:/Users/rskrn/Desktop/agentchatrr/test_samples/bee_movie.srt"
    }
    
    print("POSTing /extract...")
    resp = requests.post(f"{BASE_URL}/extract", json=payload)
    if resp.status_code != 202:
        print(f"FAILED: {resp.status_code} - {resp.text}")
        return
    
    job_id = resp.json()["job_id"]
    print(f"Job started: {job_id}")
    
    # 2. Poll for status
    for _ in range(10):
        print(f"Polling /jobs/{job_id}...")
        resp = requests.get(f"{BASE_URL}/jobs/{job_id}")
        job = resp.json()
        status = job["status"]
        print(f"Status: {status} | Stage: {job.get('stage')}")
        
        if status == "succeeded":
            print("\nSUCCESS! Verifying source block...")
            source = job.get("source")
            print(f"Source Block: {source}")
            assert source["provider"] == "local_file"
            assert source["rights_status"] == "allowed_with_conditions"
            print("UI Verification Pass: PASSED")
            return
        elif status == "failed":
            print(f"FAILED: {job.get('error')}")
            return
        
        time.sleep(2)
    
    print("TIMED OUT")

if __name__ == "__main__":
    time.sleep(5) # wait for server
    test_ui_flow()
