"""
supabase_client.py
HCI Assessment Platform — Supabase Database Client

Purpose:
  - Centralized database operations for assessment_responses table
  - UPSERT (insert or update) assessment data
  - Retrieve stored assessments and results
  - Update payment status
  - Cache management

All Supabase operations go through this module.
No raw SQL or connection logic in api.py.
"""

import os
import json
from datetime import datetime
from typing import Optional, Dict, Any


class SupabaseClient:
    """Client for Supabase database operations."""
    
    def __init__(self, url: Optional[str] = None, key: Optional[str] = None):
        """
        Initialize Supabase client.
        
        Args:
            url (str, optional): Supabase URL. Defaults to SUPABASE_URL env var
            key (str, optional): Supabase API key. Defaults to SUPABASE_KEY env var
        """
        self.url = url or os.environ.get('SUPABASE_URL')
        self.key = key or os.environ.get('SUPABASE_KEY')
        
        if not self.url or not self.key:
            raise RuntimeError('SUPABASE_URL and SUPABASE_KEY environment variables required')
        
        self.base_url = f'{self.url}/rest/v1'
        self.headers = {
            'apikey': self.key,
            'Authorization': f'Bearer {self.key}',
            'Content-Type': 'application/json',
        }
    
    def store_assessment(self, session_id: str, responses: Dict, demographics: Dict,
                        full_results: Dict, report_email: Optional[str] = None,
                        consent: bool = False, consent_timestamp: Optional[str] = None) -> Dict[str, Any]:
        """
        Store or update assessment response in Supabase (UPSERT).
        
        Stores both the raw responses and the computed full_results.
        If session_id already exists, updates the row instead of creating a new one.
        
        Args:
            session_id (str): Unique assessment session identifier
            responses (dict): Raw 39 question responses {trust_q1: 5, ...}
            demographics (dict): Age, gender, country, frequency
            full_results (dict): Output from scoring_engine (dimension_scores, gaps, etc)
            report_email (str, optional): Email for report delivery
            consent (bool): Research consent status
            consent_timestamp (str, optional): ISO timestamp of consent
        
        Returns:
            dict: {success: bool, message: str, session_id: str}
        """
        try:
            import urllib.request
            import urllib.parse
            
            # Build UPSERT payload
            payload = {
                'session_id': session_id,
                'responses': responses,
                'demographics': demographics,
                'full_results': full_results,
                'consent': consent,
                'updated_at': datetime.utcnow().isoformat()
            }
            
            if report_email:
                payload['report_email'] = report_email
            if consent_timestamp:
                payload['consent_timestamp'] = consent_timestamp
            
            # POST to Supabase REST API with ON CONFLICT resolution
            body = json.dumps(payload).encode('utf-8')
            url = f'{self.base_url}/assessment_responses'
            
            headers = dict(self.headers)
            headers['Prefer'] = 'resolution=merge-duplicates'  # Supabase UPSERT via merge
            
            req = urllib.request.Request(
                url,
                data=body,
                headers=headers,
                method='POST'
            )
            
            response = urllib.request.urlopen(req, timeout=10)
            response.read()  # Consume response
            
            return {
                'success': True,
                'message': f'Assessment stored/updated for session {session_id}',
                'session_id': session_id
            }
        
        except Exception as e:
            print(f'store_assessment failed: {e}')
            return {
                'success': False,
                'message': f'Failed to store assessment: {str(e)}',
                'session_id': session_id
            }
    
    def get_assessment(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve stored assessment by session_id.
        
        Args:
            session_id (str): Unique assessment session identifier
        
        Returns:
            dict: Assessment record with all fields, or None if not found
        """
        try:
            import urllib.request
            import urllib.parse
            
            url = (
                f'{self.base_url}/assessment_responses'
                f'?session_id=eq.{urllib.parse.quote(session_id)}'
                f'&select=*'
            )
            
            req = urllib.request.Request(
                url,
                headers=self.headers,
                method='GET'
            )
            
            response = urllib.request.urlopen(req, timeout=10)
            data = json.loads(response.read())
            
            if data and len(data) > 0:
                return data[0]
            return None
        
        except Exception as e:
            print(f'get_assessment failed: {e}')
            return None
    
    def get_full_results(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve only the full_results for a session.
        
        Used by /premium endpoint to get scoring results without fetching entire row.
        
        Args:
            session_id (str): Unique assessment session identifier
        
        Returns:
            dict: Full results (dimension_scores, perception_gaps, rare_combinations) or None
        """
        try:
            assessment = self.get_assessment(session_id)
            if assessment and assessment.get('full_results'):
                return assessment['full_results']
            return None
        except Exception as e:
            print(f'get_full_results failed: {e}')
            return None
    
    def mark_as_paid(self, session_id: str, stripe_session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Update payment status to paid.
        
        Called by Stripe webhook handler when payment confirmed.
        
        Args:
            session_id (str): Unique assessment session identifier
            stripe_session_id (str, optional): Stripe checkout session ID for reference
        
        Returns:
            dict: {success: bool, message: str}
        """
        try:
            import urllib.request
            import urllib.parse
            
            # Build PATCH payload
            payload = {
                'paid': True,
                'paid_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            if stripe_session_id:
                payload['stripe_session_id'] = stripe_session_id
            
            body = json.dumps(payload).encode('utf-8')
            url = (
                f'{self.base_url}/assessment_responses'
                f'?session_id=eq.{urllib.parse.quote(session_id)}'
            )
            
            headers = dict(self.headers)
            headers['Prefer'] = 'return=minimal'
            
            req = urllib.request.Request(
                url,
                data=body,
                headers=headers,
                method='PATCH'
            )
            
            urllib.request.urlopen(req, timeout=10)
            
            return {
                'success': True,
                'message': f'Marked session {session_id} as paid'
            }
        
        except Exception as e:
            print(f'mark_as_paid failed (non-critical): {e}')
            # Non-fatal: don't block report generation if this fails
            return {
                'success': False,
                'message': f'Failed to mark as paid: {str(e)}'
            }
    
    def update_report(self, session_id: str, report_html: Optional[Dict] = None,
                     report_pdf_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Update cached report after generation.
        
        Called after report_generator and report_pdf complete.
        
        Args:
            session_id (str): Unique assessment session identifier
            report_html (dict, optional): Full report HTML (cached)
            report_pdf_url (str, optional): URL to PDF in Supabase Storage
        
        Returns:
            dict: {success: bool, message: str}
        """
        try:
            import urllib.request
            import urllib.parse
            
            # Build PATCH payload
            payload = {'updated_at': datetime.utcnow().isoformat()}
            
            if report_html is not None:
                payload['report_html'] = report_html
            if report_pdf_url is not None:
                payload['report_pdf_url'] = report_pdf_url
            
            body = json.dumps(payload).encode('utf-8')
            url = (
                f'{self.base_url}/assessment_responses'
                f'?session_id=eq.{urllib.parse.quote(session_id)}'
            )
            
            headers = dict(self.headers)
            headers['Prefer'] = 'return=minimal'
            
            req = urllib.request.Request(
                url,
                data=body,
                headers=headers,
                method='PATCH'
            )
            
            urllib.request.urlopen(req, timeout=10)
            
            return {
                'success': True,
                'message': f'Updated report for session {session_id}'
            }
        
        except Exception as e:
            print(f'update_report failed: {e}')
            return {
                'success': False,
                'message': f'Failed to update report: {str(e)}'
            }
    
    def get_cached_report(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Check if a report is already cached (prevent duplicate generation).
        
        Args:
            session_id (str): Unique assessment session identifier
        
        Returns:
            dict: Cached report_html if exists, None otherwise
        """
        try:
            assessment = self.get_assessment(session_id)
            if assessment and assessment.get('report_html'):
                return assessment['report_html']
            return None
        except Exception as e:
            print(f'get_cached_report failed: {e}')
            return None


# Singleton instance (created once at startup)
_client_instance = None


def get_supabase_client() -> SupabaseClient:
    """
    Get or create Supabase client singleton.
    
    Returns:
        SupabaseClient: Singleton instance
    """
    global _client_instance
    if _client_instance is None:
        _client_instance = SupabaseClient()
    return _client_instance
