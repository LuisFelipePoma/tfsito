import requests
from src.utils.logger import logger
from typing import Dict, List, Optional, Any
from src.config import config


class OpenfireAPI:
    """REST API client for Openfire XMPP server"""

    def __init__(self):
        self.base_url = (
            f"http://{config.openfire_host}:{config.openfire_port}/plugins/restapi/v1"
        )
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": "6G4ee93oOJEc5ccE",
        }

    def create_user(
        self,
        username: str,
        password: str,
        name: Optional[str] = None,
        email: Optional[str] = None,
    ) -> bool:
        """Create a new user in Openfire"""
        url = f"{self.base_url}/users"

        user_data = {
            "username": username,
            "password": password,
            "name": name or username,
            "email": email or f"{username}@{config.openfire_domain}",
        }

        try:
            response = requests.post(url, json=user_data, headers=self.headers)
            if response.status_code == 201:
                logger.info(f"User {username} created successfully")
                return True
            elif response.status_code == 409:
                logger.info(f"User {username} already exists")
                return True
            else:
                logger.error(
                    f"Failed to create user {username}: {response.status_code} - {response.text}"
                )
                return False
        except Exception as e:
            logger.error(f"Exception creating user {username}: {e}")
            return False

    def delete_user(self, username: str) -> bool:
        """Delete a user from Openfire"""
        url = f"{self.base_url}/users/{username}"

        try:
            response = requests.delete(url, headers=self.headers)
            if response.status_code == 200:
                logger.info(f"User {username} deleted successfully")
                return True
            else:
                logger.error(
                    f"Failed to delete user {username}: {response.status_code}"
                )
                return False
        except Exception as e:
            logger.error(f"Exception deleting user {username}: {e}")
            return False

    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user information"""
        url = f"{self.base_url}/users/{username}"

        try:
            response = requests.get(url)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get user {username}: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Exception getting user {username}: {e}")
            return None

    def list_users(self) -> List[Dict[str, Any]]:
        """List all users"""
        url = f"{self.base_url}/users"

        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                return data.get("users", [])
            else:
                logger.error(f"Failed to list users: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Exception listing users: {e}")
            return []
        
    def get_taxis_jid(self)-> List[str]:
        online_users = self.get_online_users()

        """Get list of taxis JIDs"""
        taxis_jid = []
        for user in online_users:
            if user.__contains__("taxi_"):
                taxis_jid.append(f"{user}@{config.openfire_container}")        
        return taxis_jid

    def get_online_users(self) -> List[str]:
        """Get list of currently online users"""
        url = f"{self.base_url}/sessions"

        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                sessions = data.get("sessions", [])
                return [
                    session.get("username")
                    for session in sessions
                    if session.get("username")
                ]
            else:
                logger.error(f"Failed to get online users: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Exception getting online users: {e}")
            return []

    def send_broadcast_message(self, message: str) -> bool:
        """Send a broadcast message to all online users"""
        url = f"{self.base_url}/messages/users"

        message_data = {"body": message}

        try:
            response = requests.post(url, json=message_data, headers=self.headers)
            if response.status_code == 200:
                logger.info("Broadcast message sent successfully")
                return True
            else:
                logger.error(
                    f"Failed to send broadcast message: {response.status_code}"
                )
                return False
        except Exception as e:
            logger.error(f"Exception sending broadcast message: {e}")
            return False

    def health_check(self) -> bool:
        """Check if Openfire server is responding"""
        url = f"{self.base_url}/system/properties"
        print(url)
        try:
            response = requests.get(url, headers=self.headers)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Openfire health check failed: {e}")
            return False


# Global API instance
openfire_api = OpenfireAPI()
