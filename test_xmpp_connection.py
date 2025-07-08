#!/usr/bin/env python3
"""
Test XMPP Connection to OpenFire
===============================

Test the actual XMPP connection to determine the correct domain and credentials
"""

import asyncio
import aioxmpp
import aioxmpp.structs
import sys
import logging

logging.basicConfig(level=logging.DEBUG)

async def test_xmpp_connection():
    """Test XMPP connection with different domain configurations"""
    
    domains_to_test = [
        "localhost",
        "taxisystem.local", 
        "openfire",
        "127.0.0.1"
    ]
    
    passwords_to_test = ["123", "admin", "password"]
    
    print("🔍 Testing XMPP Connection to OpenFire")
    print("=" * 50)
    
    for domain in domains_to_test:
        for password in passwords_to_test:
            try:
                print(f"\n📡 Testing: admin@{domain} with password '{password}'")
                
                # Create JID
                jid = aioxmpp.structs.JID.fromstr(f"admin@{domain}")
                
                # Create client
                async with aioxmpp.PresenceManagedClient(
                    jid,
                    aioxmpp.make_security_layer(password)
                ) as client:
                    print(f"✅ SUCCESS: Connected to {domain} with password '{password}'")
                    
                    # Get server info
                    print(f"   - JID: {client.local_jid}")
                    print(f"   - Connected: {client.established}")
                    
                    return domain, password
                    
            except Exception as e:
                print(f"❌ Failed: {domain} with '{password}' - {type(e).__name__}: {str(e)[:100]}")
                continue
    
    print(f"\n❌ No working XMPP configuration found!")
    return None, None

async def main():
    domain, password = await test_xmpp_connection()
    
    if domain and password:
        print(f"\n🎉 Working Configuration Found:")
        print(f"   - Domain: {domain}")
        print(f"   - Password: {password}")
        print(f"\n📝 Update your config.py:")
        print(f"   openfire_domain = \"{domain}\"")
        print(f"   openfire_admin_password = \"{password}\"")
    else:
        print(f"\n💡 Troubleshooting steps:")
        print(f"   1. Check if OpenFire is running: docker ps")
        print(f"   2. Check OpenFire logs: docker logs openfire")
        print(f"   3. Access admin console: http://localhost:9090")
        print(f"   4. Verify XMPP domain in OpenFire settings")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Test cancelled")
    except Exception as e:
        print(f"\n❌ Test error: {e}")
        print("\n💡 This might indicate XMPP server configuration issues")
