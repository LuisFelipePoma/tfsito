#!/usr/bin/env python3
"""
Quick OpenFire REST API Test
===========================

Test if we can create users via OpenFire REST API
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from services.openfire_api import OpenfireAPI
from config import SimulationConfig

def main():
    config = SimulationConfig()
    
    print("🔥 Testing OpenFire REST API Integration")
    print("=" * 50)
    
    # Initialize API
    api = OpenfireAPI()
    
    print(f"📡 Testing connection to {config.openfire_host}:{config.openfire_port}")
    
    # Test creating a test user
    test_user = "test_taxi_001"
    test_password = "password123"
    
    try:
        print(f"👤 Creating test user: {test_user}")
        success = api.create_user(test_user, test_password, f"Test Taxi Agent")
        
        if success:
            print(f"✅ Successfully created user: {test_user}")
            
            # Test getting user info
            print(f"🔍 Getting user info for: {test_user}")
            user_info = api.get_user(test_user)
            if user_info:
                print(f"✅ Retrieved user info: {user_info}")
            else:
                print(f"⚠️  Could not retrieve user info")
                
        else:
            print(f"❌ Failed to create user: {test_user}")
            
    except Exception as e:
        print(f"❌ Error during API test: {e}")
        return 1
    
    print(f"\n🎯 OpenFire REST API test completed!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
