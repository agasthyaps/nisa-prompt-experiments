#!/usr/bin/env python3
"""
Test script to verify your Chat Arena v2 setup.
Run this before starting the main application to ensure everything is configured correctly.
"""

import os
import sys
import json
from dotenv import load_dotenv
import openai

def test_setup():
    print("🔍 Testing Chat Arena v2 Setup...\n")
    
    # Test 1: Environment
    print("1. Checking environment setup...")
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("❌ OPENAI_API_KEY not found in environment!")
        print("   Please create a .env file with: OPENAI_API_KEY=your_key_here")
        return False
    
    if api_key.startswith("sk-"):
        print("✅ OpenAI API key found")
    else:
        print("⚠️  API key found but doesn't start with 'sk-' - might be invalid")
    
    # Test 2: OpenAI Connection
    print("\n2. Testing OpenAI API connection...")
    openai.api_key = api_key
    
    try:
        # Test with a simple completion
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Say 'Hello, Chat Arena!'"}],
            max_tokens=20
        )
        print("✅ OpenAI API connection successful")
        print(f"   Response: {response.choices[0].message.content}")
    except Exception as e:
        print(f"❌ OpenAI API error: {e}")
        return False
    
    # Test 3: File System
    print("\n3. Checking file system setup...")
    data_dir = "data"
    
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        print(f"✅ Created {data_dir}/ directory")
    else:
        print(f"✅ {data_dir}/ directory exists")
    
    # Test 4: Model Availability
    print("\n4. Checking model availability...")
    test_models = ["gpt-4", "gpt-4-turbo-preview", "gpt-3.5-turbo"]
    
    for model in test_models:
        try:
            response = openai.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5
            )
            print(f"✅ {model} is available")
        except openai.NotFoundError:
            print(f"❌ {model} is not available on your account")
        except Exception as e:
            print(f"⚠️  {model} error: {e}")
    
    # Test 5: Dependencies
    print("\n5. Checking Python dependencies...")
    try:
        import streamlit
        print("✅ Streamlit is installed")
    except ImportError:
        print("❌ Streamlit not installed - run: pip install streamlit")
        return False
    
    print("\n✨ Setup test complete!")
    print("\nYou can now run: streamlit run chat_arena_v2.py")
    return True

if __name__ == "__main__":
    success = test_setup()
    sys.exit(0 if success else 1) 