#!/usr/bin/env python3
"""
Test OpenFire Connection and Configuration
=========================================

This script tests the connection to OpenFire server and helps configure
the distributed taxi system.
"""

import requests
import sys
import os

def test_openfire_connection(host, port=9090):
    """Test connection to OpenFire server"""
    try:
        # Test basic web interface
        response = requests.get(f"http://{host}:{port}/", timeout=5)
        print(f"✅ OpenFire web interface accessible at {host}:{port}")
        print(f"   Status: {response.status_code}")
        
        # Test if it's actually OpenFire
        if "openfire" in response.text.lower() or "xmpp" in response.text.lower():
            print("✅ Confirmed: This is an OpenFire/XMPP server")
        
        # Test REST API
        try:
            api_response = requests.get(f"http://{host}:{port}/plugins/restapi/v1/system/properties", timeout=5)
            if api_response.status_code == 200:
                print("✅ REST API is accessible")
            else:
                print(f"⚠️  REST API returned status: {api_response.status_code}")
        except Exception as e:
            print(f"⚠️  REST API test failed: {e}")
            print("   (This might be normal if REST API plugin is not installed)")
        
        return True
        
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to {host}:{port}")
        return False
    except requests.exceptions.Timeout:
        print(f"❌ Connection to {host}:{port} timed out")
        return False
    except Exception as e:
        print(f"❌ Error testing {host}:{port}: {e}")
        return False

def main():
    print("🔍 Testing OpenFire Connection")
    print("=" * 40)
    
    # Test different possible locations
    hosts_to_test = [
        "localhost",
        "127.0.0.1", 
        "192.168.1.100"
    ]
    
    working_host = None
    
    for host in hosts_to_test:
        print(f"\n📡 Testing {host}:9090...")
        if test_openfire_connection(host):
            working_host = host
            break
    
    if working_host:
        print(f"\n🎉 OpenFire is accessible at: {working_host}:9090")
        print(f"\n📝 To use this OpenFire server, update your configuration:")
        print(f"   - Set OPENFIRE_HOST={working_host}")
        print(f"   - Set OPENFIRE_PORT=9090")
        print(f"   - Set OPENFIRE_XMPP_PORT=5222")
        
        # Create environment file
        env_content = f"""# OpenFire Configuration for Taxi System
OPENFIRE_HOST={working_host}
OPENFIRE_PORT=9090
OPENFIRE_XMPP_PORT=5222
OPENFIRE_DOMAIN=taxisystem.local
"""
        
        with open(".env", "w") as f:
            f.write(env_content)
        
        print(f"\n✅ Created .env file with working configuration")
        
    else:
        print(f"\n❌ OpenFire is not accessible on any tested hosts")
        print(f"\n💡 Troubleshooting steps:")
        print(f"   1. Start OpenFire with Docker: docker-compose -f docker-compose-distributed.yml up openfire")
        print(f"   2. Check if OpenFire is running: docker ps")
        print(f"   3. Check OpenFire logs: docker logs taxi_openfire")
        
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
