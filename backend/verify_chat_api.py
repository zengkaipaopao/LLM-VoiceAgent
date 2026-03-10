"""
Test script for LLM chat API.

Run this to verify the backend is working correctly.
"""
import requests
import json

BASE_URL = "http://localhost:8000/api/v1"


def test_list_templates():
    """Test listing prompt templates."""
    print("\n=== Testing: List Templates ===")
    response = requests.get(f"{BASE_URL}/prompts")
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        res_data = response.json()
        data = res_data.get("data", {})
        print(f"Found {data.get('total', 0)} templates:")
        for template in data.get('templates', []):
            print(f"  - {template['code']}: {template['name']}")
    else:
        print(f"Error: {response.text}")


def test_get_template():
    """Test getting a specific template."""
    print("\n=== Testing: Get Template ===")
    response = requests.get(f"{BASE_URL}/prompts") # Fetch all to find the ID of 'hotel_booking'
    if response.status_code == 200:
        data = response.json().get("data", {})
        templates = data.get('templates', [])
        hotel_booking = next((t for t in templates if t['code'] == 'hotel_booking'), None)
        if hotel_booking:
            print(f"Status: 200")
            print(f"Template: {hotel_booking['name']}")
            print(f"Category: {hotel_booking['category']}")
            print(f"System Prompt: {hotel_booking['system_prompt'][:100]}...")
            return
    print(f"Error: Could not find hotel_booking template or request failed.")


def test_chat():
    """Test chat endpoint."""
    print("\n=== Testing: Chat ===")
    payload = {
        "message": "我想预订明天下午3点的酒店",
        "template_code": "hotel_booking",
        "provider": "gemini"
    }
    
    print(f"Sending: {payload['message']}")
    response = requests.post(f"{BASE_URL}/chat", json=payload)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        res_data = response.json()
        data = res_data.get("data", {})
        print(f"Response: {data.get('response')}")
        print(f"Call ID: {data.get('call_id')}")
        return data.get('call_id')
    else:
        print(f"Error: {response.text}")
        return None


def test_extract(call_id):
    """Test extraction endpoint."""
    print("\n=== Testing: Extract Appointment ===")
    payload = {
        "call_id": call_id
    }
    
    response = requests.post(f"{BASE_URL}/chat/extract", json=payload)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        res_data = response.json()
        data = res_data.get("data", {})
        print(f"Success: {res_data.get('success')}")
        print(f"Confidence: {data.get('confidence')}")
        print(f"Extracted Data: {json.dumps(data.get('extracted_data'), indent=2, ensure_ascii=False)}")
    else:
        print(f"Error: {response.text}")


if __name__ == "__main__":
    print("=" * 60)
    print("LLM Chat API Test")
    print("=" * 60)
    
    # Test templates
    test_list_templates()
    test_get_template()
    
    # Note: Chat and extraction tests require Google API key
    print("\n" + "=" * 60)
    print("Note: Chat tests require GOOGLE_API_KEY in .env file")
    print("=" * 60)
    
    # Uncomment to test chat (requires API key)
    # call_id = test_chat()
    # if call_id:
    #     test_extract(call_id)
