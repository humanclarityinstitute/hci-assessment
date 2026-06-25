"""
stripe_config.py
HCI Assessment Platform — Stripe Payment Configuration

Purpose:
  - Create Stripe checkout sessions ($29 USD report)
  - Verify webhook signatures from Stripe
  - Handle payment success events
  - Resolve product prices from Stripe

All Stripe operations go through this module.
No raw Stripe API calls in api.py.
"""

import os
import json
import hmac
import hashlib
from typing import Optional, Dict, Any


class StripeConfig:
    """Stripe payment processor."""
    
    def __init__(self, secret_key: Optional[str] = None):
        """
        Initialize Stripe config.
        
        Args:
            secret_key (str, optional): Stripe secret key. Defaults to STRIPE_SECRET_KEY env var
        """
        self.secret_key = secret_key or os.environ.get('STRIPE_SECRET_KEY')
        self.webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')
        
        if not self.secret_key:
            raise RuntimeError('STRIPE_SECRET_KEY environment variable required')
        
        # Price lookup key — configured in Stripe dashboard
        # The actual amount/currency is managed in Stripe, not in code
        self.price_lookup_key = os.environ.get('REPORT_PRICE_LOOKUP_KEY', 'hci_report_standard')
        
        # URLs for checkout flow
        self.base_report_url = os.environ.get(
            'REPORT_BASE_URL',
            'https://humanclarityinstitute.com/ai-assessment/report'
        )
        self.success_url = self.base_report_url + '?stripe_session_id={CHECKOUT_SESSION_ID}'
        self.cancel_url = os.environ.get(
            'CHECKOUT_CANCEL_URL',
            'https://humanclarityinstitute.com/ai-assessment/results'
        )
    
    def create_checkout_session(self, session_id: str, email: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a Stripe Checkout Session for report purchase.
        
        Args:
            session_id (str): Assessment session ID (used for tracking)
            email (str, optional): Customer email (optional)
        
        Returns:
            dict: {
                success: bool,
                session_id: str,  # Stripe's checkout session ID
                url: str,  # URL to redirect user to
                message: str
            }
        """
        try:
            # Step 1: Resolve price ID from lookup key
            price_id = self._resolve_price_id()
            if not price_id:
                return {
                    'success': False,
                    'session_id': None,
                    'url': None,
                    'message': 'Could not determine product price. Please try again later.'
                }
            
            # Step 2: Create checkout session
            fields = {
                'mode': 'payment',
                'success_url': self.success_url,
                'cancel_url': self.cancel_url,
                'line_items[0][price]': price_id,
                'line_items[0][quantity]': '1',
                'billing_address_collection': 'auto',
                'client_reference_id': session_id,  # Link payment back to assessment session
            }
            
            # Optional: collect customer email for delivery
            if email:
                fields['customer_email'] = email
            
            # Call Stripe API
            response_data = self._stripe_post('https://api.stripe.com/v1/checkout/sessions', fields)
            
            if 'id' in response_data:
                return {
                    'success': True,
                    'session_id': response_data['id'],
                    'url': response_data.get('url'),
                    'message': 'Checkout session created'
                }
            else:
                return {
                    'success': False,
                    'session_id': None,
                    'url': None,
                    'message': 'Failed to create checkout session'
                }
        
        except Exception as e:
            print(f'create_checkout_session failed: {e}')
            return {
                'success': False,
                'session_id': None,
                'url': None,
                'message': f'Checkout error: {str(e)}'
            }
    
    def verify_webhook_signature(self, payload: str, signature: str) -> bool:
        """
        Verify Stripe webhook signature.
        
        Called on POST /webhook/stripe to ensure the payload is authentic.
        
        Args:
            payload (str): Raw request body (unparsed JSON)
            signature (str): Stripe-Signature header value
        
        Returns:
            bool: True if signature is valid, False otherwise
        """
        if not self.webhook_secret:
            print('STRIPE_WEBHOOK_SECRET not configured — cannot verify webhook')
            return False
        
        try:
            # Stripe signs with: HMAC-SHA256(secret, payload)
            timestamp, signed_hash = signature.split(',')[0].split('=')[1], signature.split('t=')[1].split(',')[0]
            signed_content = f'{timestamp}.{payload}'
            
            computed_hash = hmac.new(
                self.webhook_secret.encode(),
                signed_content.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Compare computed hash with Stripe's signature (constant-time comparison)
            return hmac.compare_digest(computed_hash, signed_hash)
        
        except Exception as e:
            print(f'Webhook signature verification failed: {e}')
            return False
    
    def parse_webhook_event(self, payload: str) -> Optional[Dict[str, Any]]:
        """
        Parse Stripe webhook event payload.
        
        Args:
            payload (str): Raw JSON payload from Stripe
        
        Returns:
            dict: Parsed event, or None if invalid JSON
        """
        try:
            return json.loads(payload)
        except Exception as e:
            print(f'Failed to parse webhook payload: {e}')
            return None
    
    def handle_checkout_completed(self, event: Dict[str, Any]) -> Optional[str]:
        """
        Extract session data from checkout.session.completed event.
        
        Args:
            event (dict): Stripe event object
        
        Returns:
            str: Stripe session ID, or None if not found
        """
        try:
            session = event.get('data', {}).get('object', {})
            stripe_session_id = session.get('id')
            customer_email = session.get('customer_email')
            
            return {
                'stripe_session_id': stripe_session_id,
                'customer_email': customer_email,
                'amount_paid': session.get('amount_total'),  # in cents
                'currency': session.get('currency'),
            }
        except Exception as e:
            print(f'Failed to extract checkout data: {e}')
            return None
    
    def _resolve_price_id(self) -> Optional[str]:
        """
        Resolve active Stripe Price ID from lookup key.
        
        Price can be changed in Stripe dashboard without code change.
        This looks up the current active price for the given lookup key.
        
        Returns:
            str: Price ID, or None if not found/error
        """
        try:
            import urllib.request
            import urllib.parse
            
            # Query Stripe Prices API
            query = urllib.parse.urlencode({
                'lookup_keys[]': self.price_lookup_key,
                'active': 'true',
                'limit': '1',
            })
            
            url = f'https://api.stripe.com/v1/prices?{query}'
            req = urllib.request.Request(
                url,
                headers={'Authorization': f'Bearer {self.secret_key}'},
            )
            
            response = urllib.request.urlopen(req, timeout=15)
            data = json.loads(response.read())
            
            prices = data.get('data', [])
            if prices:
                return prices[0]['id']
            
            print(f'No active price found for lookup key {self.price_lookup_key}')
            return None
        
        except Exception as e:
            print(f'Price lookup failed: {e}')
            return None
    
    def _stripe_post(self, url: str, fields: Dict[str, str]) -> Dict[str, Any]:
        """
        POST form-encoded data to Stripe API.
        
        Args:
            url (str): Stripe API endpoint
            fields (dict): Form fields to POST
        
        Returns:
            dict: Parsed JSON response
        
        Raises:
            Exception: On HTTP error or invalid response
        """
        try:
            import urllib.request
            import urllib.parse
            
            data = urllib.parse.urlencode(fields).encode('utf-8')
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    'Authorization': f'Bearer {self.secret_key}',
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                method='POST',
            )
            
            response = urllib.request.urlopen(req, timeout=15)
            return json.loads(response.read())
        
        except urllib.error.HTTPError as e:
            error_body = e.read().decode()
            print(f'Stripe API error: {error_body}')
            raise Exception(f'Stripe API error: {error_body}')
        except Exception as e:
            raise Exception(f'Stripe request failed: {str(e)}')


# Singleton instance (created once at startup)
_stripe_instance = None


def get_stripe_config() -> StripeConfig:
    """
    Get or create Stripe config singleton.
    
    Returns:
        StripeConfig: Singleton instance
    """
    global _stripe_instance
    if _stripe_instance is None:
        _stripe_instance = StripeConfig()
    return _stripe_instance
