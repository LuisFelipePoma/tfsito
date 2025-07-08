#!/usr/bin/env python3
"""
Simple SPADE XMPP Connection Test
================================

Test SPADE connection to OpenFire with different configurations
"""

import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

try:
    from spade.agent import Agent
    from spade.behaviour import OneShotBehaviour
    SPADE_AVAILABLE = True
except ImportError:
    SPADE_AVAILABLE = False

class TestAgent(Agent):
    """Simple test agent for XMPP connection"""
    
    async def setup(self):
        print(f"✅ Agent setup complete: {self.jid}")
        
    class TestBehaviour(OneShotBehaviour):
        async def run(self):
            print(f"✅ Agent behavior running: {self.agent.jid}")

async def test_spade_connection():
    """Test SPADE connection with different configurations"""
    
    if not SPADE_AVAILABLE:
        print("❌ SPADE not available")
        return False
    
    # Different domain/password combinations to test
    test_configs = [
        ("localhost", "123"),
        ("localhost", "admin"),
        ("taxisystem.local", "123"),
        ("127.0.0.1", "123"),
    ]
    
    print("🔍 Testing SPADE XMPP Connection")
    print("=" * 40)
    
    for domain, password in test_configs:
        jid = f"test_agent@{domain}"
        print(f"\n📡 Testing: {jid} with password '{password}'")
        
        try:
            # Create test agent
            agent = TestAgent(jid, password)
            agent.add_behaviour(agent.TestBehaviour())
            
            # Try to start with timeout
            print(f"   - Creating agent...")
            start_task = asyncio.create_task(agent.start())
            
            try:
                await asyncio.wait_for(start_task, timeout=10.0)
                print(f"✅ SUCCESS: Connected to {domain}")
                
                # Stop the agent
                await agent.stop()
                print(f"   - Agent stopped cleanly")
                
                return domain, password
                
            except asyncio.TimeoutError:
                print(f"❌ TIMEOUT: Connection to {domain} timed out")
                try:
                    await agent.stop()
                except:
                    pass
                
            except Exception as e:
                print(f"❌ CONNECTION ERROR: {type(e).__name__}: {str(e)[:100]}")
                try:
                    await agent.stop()
                except:
                    pass
                
        except Exception as e:
            print(f"❌ SETUP ERROR: {type(e).__name__}: {str(e)[:100]}")
            continue
    
    print(f"\n❌ No working SPADE configuration found!")
    return None, None

async def main():
    domain, password = await test_spade_connection()
    
    if domain and password:
        print(f"\n🎉 Working SPADE Configuration Found:")
        print(f"   - Domain: {domain}")
        print(f"   - Password: {password}")
        print(f"\n📝 Update your configuration:")
        print(f"   openfire_domain = \"{domain}\"")
        print(f"   openfire_admin_password = \"{password}\"")
        
        print(f"\n✅ You can now run: deploy_distributed.bat coordinator")
        
    else:
        print(f"\n💡 Possible solutions:")
        print(f"   1. Check OpenFire container: docker logs openfire")
        print(f"   2. Restart OpenFire: docker restart openfire") 
        print(f"   3. Check OpenFire admin console: http://localhost:9090")
        print(f"   4. Verify XMPP domain configuration in OpenFire")
        print(f"   5. Check firewall/port 5222 accessibility")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Test cancelled")
    except Exception as e:
        print(f"\n❌ Test error: {e}")
        import traceback
        traceback.print_exc()
