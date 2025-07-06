import datetime
from spade.agent import Agent
import logging
from spade.message import Message
from spade.behaviour import PeriodicBehaviour

logger = logging.getLogger(__name__)


class SurvivorAgent(Agent):
    """SPADE agent representing a survivor in the post-apocalyptic world"""

    def __init__(self, jid: str, password: str, host_id: str):
        super().__init__(jid, password, verify_security=False)
        self.agent_id = jid.split("@")[0]
        self.host_id = host_id

    class InformBehav(PeriodicBehaviour):
        async def run(self):
            print(f"PeriodicSenderBehaviour running at {datetime.datetime.now().time()}: {self.counter}")
            msg = Message(to=self.get("receiver_jid"))  # Instantiate the message
            msg.body = "Hello World"  # Set the message content

            await self.send(msg)
            print("Message sent!")

            if self.counter == 5:
                self.kill()
            self.counter += 1

        async def on_end(self):
            # stop agent from behaviour
            await self.agent.stop()

        async def on_start(self):
            self.counter = 0
        
    async def setup(self):
        """Initialize agent behaviors and register with environment"""
        logger.info(f"Setting up agent {self.agent_id}")

        # Add behaviors
        start_at = datetime.datetime.now() + datetime.timedelta(seconds=5)
        b = self.InformBehav(period=2, start_at=start_at)
        self.add_behaviour(b)

        logger.info(
            f"Agent {self.agent_id} setup complete at position"
        )

    async def cleanup(self):
        """Cleanup when agent is stopping"""
        logger.info(f"Agent {self.agent_id} cleanup complete")
