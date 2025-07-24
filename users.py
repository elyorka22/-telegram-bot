import json
import os
from datetime import datetime
from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)

class UserManager:
    def __init__(self, users_file: str = "users.json"):
        self.users_file = users_file
        self.users = self.load_users()
    
    def load_users(self) -> Dict:
        """Load users from JSON file."""
        try:
            if os.path.exists(self.users_file):
                with open(self.users_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"Error loading users: {e}")
            return {}
    
    def save_users(self):
        """Save users to JSON file."""
        try:
            with open(self.users_file, 'w', encoding='utf-8') as f:
                json.dump(self.users, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving users: {e}")
    
    def register_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None) -> bool:
        """Register a new user."""
        user_id_str = str(user_id)
        
        if user_id_str in self.users:
            return False  # User already exists
        
        user_data = {
            'user_id': user_id,
            'username': username,
            'first_name': first_name,
            'last_name': last_name,
            'language': 'en',  # Default language
            'registered_at': datetime.now().isoformat(),
            'last_activity': datetime.now().isoformat(),
            'stats': {
                'words_saved': 0,
                'hashtags_created': 0,
                'hashtags_deleted': 0,
                'pdfs_generated': 0,
                'total_messages': 0
            },
            'preferences': {
                'auto_save': True,
                'notifications': True
            }
        }
        
        self.users[user_id_str] = user_data
        self.save_users()
        logger.info(f"New user registered: {user_id}")
        return True
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Get user data."""
        user_id_str = str(user_id)
        return self.users.get(user_id_str)
    
    def update_user_language(self, user_id: int, language: str):
        """Update user's language preference."""
        user_id_str = str(user_id)
        if user_id_str in self.users:
            self.users[user_id_str]['language'] = language
            self.users[user_id_str]['last_activity'] = datetime.now().isoformat()
            self.save_users()
    
    def update_user_activity(self, user_id: int):
        """Update user's last activity time."""
        user_id_str = str(user_id)
        if user_id_str in self.users:
            self.users[user_id_str]['last_activity'] = datetime.now().isoformat()
            self.users[user_id_str]['stats']['total_messages'] += 1
            self.save_users()
    
    def increment_stat(self, user_id: int, stat_name: str):
        """Increment user statistic."""
        user_id_str = str(user_id)
        if user_id_str in self.users:
            if stat_name in self.users[user_id_str]['stats']:
                self.users[user_id_str]['stats'][stat_name] += 1
                self.save_users()
    
    def get_user_stats(self, user_id: int) -> Dict:
        """Get user statistics."""
        user = self.get_user(user_id)
        if user:
            return user.get('stats', {})
        return {}
    
    def get_user_profile(self, user_id: int) -> Dict:
        """Get complete user profile."""
        user = self.get_user(user_id)
        if not user:
            return {}
        
        # Calculate additional stats
        registered_date = datetime.fromisoformat(user['registered_at'])
        days_registered = (datetime.now() - registered_date).days
        
        profile = {
            'user_id': user['user_id'],
            'username': user.get('username', 'N/A'),
            'first_name': user.get('first_name', 'N/A'),
            'last_name': user.get('last_name', ''),
            'language': user['language'],
            'registered_at': user['registered_at'],
            'days_registered': days_registered,
            'stats': user['stats'],
            'preferences': user['preferences']
        }
        
        return profile
    
    def update_user_preference(self, user_id: int, preference: str, value):
        """Update user preference."""
        user_id_str = str(user_id)
        if user_id_str in self.users:
            if 'preferences' not in self.users[user_id_str]:
                self.users[user_id_str]['preferences'] = {}
            self.users[user_id_str]['preferences'][preference] = value
            self.save_users()
    
    def get_all_users(self) -> List[Dict]:
        """Get all users (for admin purposes)."""
        return list(self.users.values())
    
    def delete_user(self, user_id: int) -> bool:
        """Delete user (for admin purposes)."""
        user_id_str = str(user_id)
        if user_id_str in self.users:
            del self.users[user_id_str]
            self.save_users()
            return True
        return False
    
    def get_users_count(self) -> int:
        """Get total number of users."""
        return len(self.users)
    
    def get_active_users(self, days: int = 7) -> List[Dict]:
        """Get users active in the last N days."""
        active_users = []
        cutoff_date = datetime.now().timestamp() - (days * 24 * 60 * 60)
        
        for user in self.users.values():
            try:
                last_activity = datetime.fromisoformat(user['last_activity']).timestamp()
                if last_activity > cutoff_date:
                    active_users.append(user)
            except:
                continue
        
        return active_users

# Global user manager instance
user_manager = UserManager() 