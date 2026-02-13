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
    response = requests.get(f"{BASE_URL}/prompt-templates/templates")
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Found {data['total']} templates:")
        for template in data['templates']:
            print(f"  - {template['code']}: {template['name']}")
    else:
        print(f"Error: {response.text}")


def test_get_template():
    """Test getting a specific template."""
    print("\n=== Testing: Get Template ===")
    response = requests.get(f"{BASE_URL}/prompt-templates/templates/hotel_booking")
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Template: {data['name']}")
        print(f"Category: {data['category']}")
        print(f"System Prompt: {data['system_prompt'][:100]}...")
    else:
        print(f"Error: {response.text}")


def test_chat():
    """Test chat endpoint."""
    print("\n=== Testing: Chat ===")
    payload = {
        "message": "我想预订明天下午3点的酒店",
        "template_code": "hotel_booking",
        "provider": "gemini"
    }
    
    print(f"Sending: {payload['message']}")
    response = requests.post(f"{BASE_URL}/chat/chat", json=payload)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Response: {data['response']}")
        print(f"Call ID: {data['call_id']}")
        return data['call_id']
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
        data = response.json()
        print(f"Success: {data['success']}")
        print(f"Confidence: {data['confidence']}")
        print(f"Extracted Data: {json.dumps(data['extracted_data'], indent=2, ensure_ascii=False)}")
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
