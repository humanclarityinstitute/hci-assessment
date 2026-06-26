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
    
    def store_assessment(self, session_id: str, **kwargs) -> Dict[str, Any]:
        """
        Store assessment responses to Supabase using the proven working pattern.
        
        Uses POST with ?on_conflict=session_id and Prefer header for upsert behavior.
        This matches the exact pattern from working api.py v5.4.
        
        Args:
            session_id: Unique session identifier
            **kwargs: All assessment data fields (responses, demographics, full_results, etc)
        
        Returns:
            Dict with 'success' key (True/False) and optional 'message' key
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
            response = urllib.request.urlopen(req, timeout=30)
            response.read()  # Consume response
            response.close()
            
            return {'success': True}
            
        except urllib.error.HTTPError as e:
            error_msg = e.read().decode('utf-8')
            print(f"HTTP Error {e.code}: {error_msg}")
            return {'success': False, 'message': f'HTTP {e.code}: {error_msg}'}
        except urllib.error.URLError as e:
            print(f"URL Error: {e.reason}")
            return {'success': False, 'message': f'URL Error: {e.reason}'}
        except Exception as e:
            print(f"Error storing assessment: {str(e)}")
            return {'success': False, 'message': str(e)}
    
    def get_assessment(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve complete assessment record by session_id.
        
        Returns the full assessment object with all fields: responses, demographics,
        full_results, email, consent, timestamp, etc.
        
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
            
            response = urllib.request.urlopen(req, timeout=30)
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
    
    def get_full_results(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve only the full_results field from an assessment.
        
        This is a convenience method for extracting just the scoring results
        without fetching the entire assessment record.
        
        Args:
            session_id: Session identifier to fetch
        
        Returns:
            Full results dictionary or None if not found
        """
        assessment = self.get_assessment(session_id)
        if assessment:
            return assessment.get('full_results')
        return None
    
    def get_cached_report(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached premium report if it exists.
        
        This checks if a premium report has already been generated and cached
        for this session_id.
        
        Args:
            session_id: Session identifier to check
        
        Returns:
            Cached report data or None if not found
        """
        assessment = self.get_assessment(session_id)
        if assessment:
            return assessment.get('cached_report')
        return None
    
    def check_session_exists(self, session_id: str) -> bool:
        """
        Check if a session already exists in Supabase.
        
        Args:
            session_id: Session identifier to check
        
        Returns:
            True if session exists, False otherwise
        """
        return self.get_assessment(session_id) is not None
    
    def mark_as_paid(self, session_id: str) -> bool:
        """
        Mark an assessment as paid (premium report purchased).
        
        Updates the assessment record to set paid=true.
        
        Args:
            session_id: Session identifier
        
        Returns:
            True if successful, False otherwise
        """
        try:
            url = f'{self.supabase_url}/rest/v1/assessment_responses?session_id=eq.{session_id}'
            
            body = json.dumps({'paid': True}).encode('utf-8')
            
            req = urllib.request.Request(
                url,
                data=body,
                headers={
                    'Content-Type': 'application/json',
                    'apikey': self.supabase_key,
                    'Authorization': f'Bearer {self.supabase_key}',
                    'Prefer': 'return=minimal',
                },
                method='PATCH'
            )
            
            response = urllib.request.urlopen(req, timeout=30)
            response.read()
            response.close()
            return True
            
        except urllib.error.HTTPError as e:
            error_details = e.read().decode('utf-8')
            print(f"Error marking as paid: HTTP {e.code}: {error_details}")
            return False
        except Exception as e:
            print(f"Error marking as paid: {type(e).__name__}: {str(e)}")
            return False
    
    def update_report(self, session_id: str, **kwargs) -> bool:
        """
        Update report-related fields for an assessment.
        
        Used to cache generated report HTML and PDF URL.
        
        Args:
            session_id: Session identifier
            **kwargs: Fields to update (report_html, report_pdf_url, etc)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            url = f'{self.supabase_url}/rest/v1/assessment_responses?session_id=eq.{session_id}'
            
            body = json.dumps(kwargs).encode('utf-8')
            
            req = urllib.request.Request(
                url,
                data=body,
                headers={
                    'Content-Type': 'application/json',
                    'apikey': self.supabase_key,
                    'Authorization': f'Bearer {self.supabase_key}',
                    'Prefer': 'return=minimal',
                },
                method='PATCH'
            )
            
            response = urllib.request.urlopen(req, timeout=30)
            response.read()
            response.close()
            return True
            
        except urllib.error.HTTPError as e:
            error_details = e.read().decode('utf-8')
            print(f"Error updating report: HTTP {e.code}: {error_details}")
            return False
        except Exception as e:
            print(f"Error updating report: {type(e).__name__}: {str(e)}")
            return False
    
    def update_assessment(self, session_id: str, **kwargs) -> bool:
        """
        Update assessment fields (payment status, stripe_session_id, etc).
        
        This updates the SAME ROW - does NOT create a new record.
        Used to mark payments and store payment IDs without duplicating data.
        
        Args:
            session_id: Session identifier
            **kwargs: Fields to update (paid, stripe_session_id, paid_at, etc)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            url = f'{self.supabase_url}/rest/v1/assessment_responses?session_id=eq.{session_id}'
            
            body = json.dumps(kwargs).encode('utf-8')
            
            req = urllib.request.Request(
                url,
                data=body,
                headers={
                    'Content-Type': 'application/json',
                    'apikey': self.supabase_key,
                    'Authorization': f'Bearer {self.supabase_key}',
                    'Prefer': 'return=minimal',
                },
                method='PATCH'
            )
            
            response = urllib.request.urlopen(req, timeout=30)
            response.read()
            response.close()
            return True
            
        except urllib.error.HTTPError as e:
            error_details = e.read().decode('utf-8')
            print(f"Error updating assessment: HTTP {e.code}: {error_details}")
            return False
        except Exception as e:
            print(f"Error updating assessment: {type(e).__name__}: {str(e)}")
            return False


def get_supabase_client() -> SupabaseClient:
    """
    Factory function to create Supabase client from environment variables.
    
    Returns:
        Initialized SupabaseClient instance
    """
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')
    
    if not supabase_url or not supabase_key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY environment variables must be set")
    
    return SupabaseClient(supabase_url, supabase_key)
