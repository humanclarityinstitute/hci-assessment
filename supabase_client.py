"""
Supabase client for HCI Assessment Platform
Handles all database operations with correct write patterns
"""

import json
import urllib.request
import urllib.error
import os
from typing import Dict, Any, Optional


class SupabaseClient:
    """Client for Supabase REST API operations"""
    
    def __init__(self, supabase_url: str, supabase_key: str):
        """
        Initialize Supabase client
        
        Args:
            supabase_url: Supabase project URL
            supabase_key: Supabase API key
        """
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
    
    def store_assessment(self, session_id: str, **kwargs) -> bool:
        """
        Store assessment responses to Supabase using the proven working pattern.
        
        Uses POST with ?on_conflict=session_id and Prefer header for upsert behavior.
        This matches the exact pattern from working api.py v5.4.
        
        Args:
            session_id: Unique session identifier
            **kwargs: All assessment data fields (responses, dimensions, scores, demographics, etc)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            url = f'{self.supabase_url}/rest/v1/assessment_responses'
            
            # Prepare the request body - bundle all kwargs with session_id
            body_dict = {
                'session_id': session_id,
                **kwargs  # Unpack all keyword arguments passed in
            }
            body = json.dumps(body_dict).encode('utf-8')
            
            # Build the URL with on_conflict parameter
            url = f'{url}?on_conflict=session_id'
            
            # Set the Prefer header for merge behavior
            prefer = 'return=minimal,resolution=merge-duplicates'
            
            # Create the request
            req = urllib.request.Request(
                url,
                data=body,
                headers={
                    'Content-Type': 'application/json',
                    'apikey': self.supabase_key,
                    'Authorization': f'Bearer {self.supabase_key}',
                    'Prefer': prefer,
                },
                method='POST'
            )
            
            # Send the request
            response = urllib.request.urlopen(req, timeout=5)
            response.read()  # Consume response
            response.close()
            
            return True
            
        except urllib.error.HTTPError as e:
            print(f"HTTP Error {e.code}: {e.read().decode('utf-8')}")
            return False
        except urllib.error.URLError as e:
            print(f"URL Error: {e.reason}")
            return False
        except Exception as e:
            print(f"Error storing assessment: {str(e)}")
            return False
    
    def fetch_assessment(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch assessment data from Supabase by session_id
        
        Args:
            session_id: Session identifier to fetch
        
        Returns:
            Dictionary of assessment data or None if not found
        """
        try:
            url = f'{self.supabase_url}/rest/v1/assessment_responses?session_id=eq.{session_id}'
            
            req = urllib.request.Request(
                url,
                headers={
                    'apikey': self.supabase_key,
                    'Authorization': f'Bearer {self.supabase_key}',
                },
                method='GET'
            )
            
            response = urllib.request.urlopen(req, timeout=5)
            data = json.loads(response.read().decode('utf-8'))
            response.close()
            
            if data and len(data) > 0:
                return data[0]
            return None
            
        except urllib.error.HTTPError as e:
            print(f"HTTP Error {e.code}: {e.read().decode('utf-8')}")
            return None
        except Exception as e:
            print(f"Error fetching assessment: {str(e)}")
            return None
    
    def check_session_exists(self, session_id: str) -> bool:
        """
        Check if a session already exists in Supabase
        
        Args:
            session_id: Session identifier to check
        
        Returns:
            True if session exists, False otherwise
        """
        return self.fetch_assessment(session_id) is not None


def get_supabase_client() -> SupabaseClient:
    """
    Factory function to create Supabase client from environment variables
    
    Returns:
        Initialized SupabaseClient instance
    """
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')
    
    if not supabase_url or not supabase_key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY environment variables must be set")
    
    return SupabaseClient(supabase_url, supabase_key)
