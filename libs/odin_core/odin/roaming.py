"""
ODIN Roaming Pass System

Implements AI-to-AI roaming with cryptographically verifiable short-lived passes.
Think telecom roaming, but for AI agents.

Key Components:
- Roaming pass generation (Home Gateway)
- Pass verification (Visited Gateway)
- HEL policy integration
- Receipt tracking
"""
import base64
import json
import time
import hashlib
import secrets
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
import yaml
import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.exceptions import InvalidSignature

# ULID generation for JTI
import ulid


@dataclass
class RoamingPassClaims:
    """Roaming pass payload claims."""
    iss: str  # Issuer (Home Gateway URL)
    sub: str  # Subject (Agent DID)
    aud: str  # Audience (Visited Gateway URL)
    realm_src: str  # Source realm
    realm_dst: str  # Destination realm
    scope: List[str]  # Allowed operations
    exp: int  # Expiration (Unix timestamp)
    nbf: int  # Not before (Unix timestamp)
    jti: str  # JWT ID (ULID)
    bind: Optional[Dict[str, str]] = None  # Optional PoP binding


@dataclass
class TrustAnchor:
    """Trust anchor configuration for roaming issuer."""
    name: str
    iss: str
    discovery: str
    realms_allowed: List[str]
    audience_allowed: List[str]
    max_ttl_seconds: int


@dataclass
class RoamingConfig:
    """Roaming configuration loaded from trust_anchors.yaml."""
    version: int
    issuers: List[TrustAnchor] = field(default_factory=list)


class RoamingPassError(Exception):
    """Base exception for roaming pass operations."""
    pass


class RoamingPassGenerator:
    """Home Gateway roaming pass generation."""
    
    def __init__(self, gateway_base_url: str, private_key: ed25519.Ed25519PrivateKey, kid: str = None):
        """
        Initialize pass generator.
        
        Args:
            gateway_base_url: This gateway's base URL (becomes iss)
            private_key: Ed25519 private key for signing
            kid: Key ID for JWKS reference
        """
        self.gateway_base_url = gateway_base_url.rstrip('/')
        self.private_key = private_key
        self.kid = kid or f"home-gw-{datetime.now().year}"
    
    def mint_pass(
        self,
        agent_did: str,
        audience: str,
        realm_dst: str,
        scope: List[str],
        ttl_seconds: int,
        realm_src: str = "default",
        bind: Optional[Dict[str, str]] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Mint a roaming pass.
        
        Args:
            agent_did: Agent DID (subject)
            audience: Visited Gateway URL
            realm_dst: Destination realm
            scope: List of allowed operations
            ttl_seconds: Time to live in seconds
            realm_src: Source realm
            bind: Optional PoP binding configuration
            
        Returns:
            (roaming_pass_token, metadata) tuple
        """
        now = int(time.time())
        exp = now + ttl_seconds
        jti = str(ulid.new())
        
        # Build claims
        claims = RoamingPassClaims(
            iss=self.gateway_base_url,
            sub=agent_did,
            aud=audience.rstrip('/'),
            realm_src=realm_src,
            realm_dst=realm_dst,
            scope=scope,
            exp=exp,
            nbf=now,
            jti=jti,
            bind=bind
        )
        
        # Create JWT-like token
        header = {
            "typ": "odin.roam.v1",
            "alg": "EdDSA",
            "kid": self.kid
        }
        
        payload = {
            "iss": claims.iss,
            "sub": claims.sub,
            "aud": claims.aud,
            "realm_src": claims.realm_src,
            "realm_dst": claims.realm_dst,
            "scope": claims.scope,
            "exp": claims.exp,
            "nbf": claims.nbf,
            "jti": claims.jti
        }
        
        if claims.bind:
            payload["bind"] = claims.bind
        
        # Encode parts
        header_b64 = base64.urlsafe_b64encode(
            json.dumps(header, separators=(',', ':')).encode()
        ).decode().rstrip('=')
        
        payload_b64 = base64.urlsafe_b64encode(
            json.dumps(payload, separators=(',', ':')).encode()
        ).decode().rstrip('=')
        
        # Sign
        signing_input = f"{header_b64}.{payload_b64}".encode()
        signature = self.private_key.sign(signing_input)
        signature_b64 = base64.urlsafe_b64encode(signature).decode().rstrip('=')
        
        # Assemble token
        token = f"{header_b64}.{payload_b64}.{signature_b64}"
        
        metadata = {
            "exp": datetime.fromtimestamp(exp, tz=timezone.utc).isoformat(),
            "jti": jti,
            "scope": scope,
            "realm_src": realm_src,
            "realm_dst": realm_dst
        }
        
        return token, metadata


class RoamingPassVerifier:
    """Visited Gateway roaming pass verification."""
    
    def __init__(self, config: RoamingConfig, gateway_base_url: str):
        """
        Initialize pass verifier.
        
        Args:
            config: Roaming configuration with trust anchors
            gateway_base_url: This gateway's base URL (for aud validation)
        """
        self.config = config
        self.gateway_base_url = gateway_base_url.rstrip('/')
        self.jwks_cache: Dict[str, Dict[str, Any]] = {}
        self.jwks_cache_ttl: Dict[str, int] = {}
    
    def verify_pass(
        self,
        roaming_pass: str,
        agent_did: str,
        target_realm: str,
        requested_operation: str
    ) -> Tuple[bool, Dict[str, Any], Optional[str]]:
        """
        Verify roaming pass.
        
        Args:
            roaming_pass: X-ODIN-Roaming-Pass header value
            agent_did: X-ODIN-Agent header value  
            target_realm: X-ODIN-Target-Realm header value
            requested_operation: Operation being requested (e.g., "mesh:post")
            
        Returns:
            (valid, claims_dict, error_reason) tuple
        """
        try:
            # Parse token
            parts = roaming_pass.split('.')
            if len(parts) != 3:
                return False, {}, "invalid_format"
            
            header_b64, payload_b64, signature_b64 = parts
            
            # Decode header
            header_padding = '=' * (4 - len(header_b64) % 4) if len(header_b64) % 4 else ''
            header_json = base64.urlsafe_b64decode(header_b64 + header_padding)
            header = json.loads(header_json)
            
            # Decode payload
            payload_padding = '=' * (4 - len(payload_b64) % 4) if len(payload_b64) % 4 else ''
            payload_json = base64.urlsafe_b64decode(payload_b64 + payload_padding)
            claims = json.loads(payload_json)
            
            # Decode signature
            sig_padding = '=' * (4 - len(signature_b64) % 4) if len(signature_b64) % 4 else ''
            signature = base64.urlsafe_b64decode(signature_b64 + sig_padding)
            
            # Validate header
            if header.get("typ") != "odin.roam.v1":
                return False, {}, "invalid_type"
            
            if header.get("alg") != "EdDSA":
                return False, {}, "unsupported_algorithm"
            
            # Find trust anchor
            trust_anchor = None
            for issuer in self.config.issuers:
                if issuer.iss == claims.get("iss"):
                    trust_anchor = issuer
                    break
            
            if not trust_anchor:
                return False, {}, "issuer_not_trusted"
            
            # Validate claims
            now = int(time.time())
            
            if claims.get("exp", 0) <= now:
                return False, {}, "expired"
            
            if claims.get("nbf", 0) > now:
                return False, {}, "not_yet_valid"
            
            if claims.get("aud") != self.gateway_base_url:
                return False, {}, "invalid_audience"
            
            if claims.get("sub") != agent_did:
                return False, {}, "agent_mismatch"
            
            if claims.get("realm_dst") != target_realm:
                return False, {}, "realm_mismatch"
            
            # Check realm authorization
            if claims.get("realm_dst") not in trust_anchor.realms_allowed:
                return False, {}, "realm_not_allowed"
            
            if self.gateway_base_url not in trust_anchor.audience_allowed:
                return False, {}, "audience_not_allowed"
            
            # Check scope
            scope = claims.get("scope", [])
            if requested_operation not in scope:
                return False, {}, "scope_mismatch"
            
            # Get public key and verify signature
            kid = header.get("kid")
            public_key = self._get_public_key(trust_anchor.discovery, kid)
            if not public_key:
                return False, {}, "key_not_found"
            
            # Verify signature
            signing_input = f"{header_b64}.{payload_b64}".encode()
            try:
                public_key.verify(signature, signing_input)
            except InvalidSignature:
                return False, {}, "sig_invalid"
            
            return True, claims, None
            
        except Exception as e:
            return False, {}, f"verification_error: {str(e)}"
    
    def _get_public_key(self, discovery_url: str, kid: str) -> Optional[ed25519.Ed25519PublicKey]:
        """Get public key from JWKS discovery."""
        try:
            # Check cache
            cache_key = f"{discovery_url}#{kid}"
            now = int(time.time())
            
            if (cache_key in self.jwks_cache and 
                cache_key in self.jwks_cache_ttl and 
                self.jwks_cache_ttl[cache_key] > now):
                jwks = self.jwks_cache[cache_key]
            else:
                # Fetch JWKS
                response = requests.get(discovery_url, timeout=10)
                response.raise_for_status()
                discovery = response.json()
                
                jwks_uri = discovery.get("jwks_uri")
                if not jwks_uri:
                    return None
                
                jwks_response = requests.get(jwks_uri, timeout=10)
                jwks_response.raise_for_status()
                jwks = jwks_response.json()
                
                # Cache for 1 hour
                self.jwks_cache[cache_key] = jwks
                self.jwks_cache_ttl[cache_key] = now + 3600
            
            # Find key
            for key in jwks.get("keys", []):
                if key.get("kid") == kid and key.get("kty") == "OKP" and key.get("crv") == "Ed25519":
                    # Decode public key
                    x = key.get("x")
                    if x:
                        x_padding = '=' * (4 - len(x) % 4) if len(x) % 4 else ''
                        public_key_bytes = base64.urlsafe_b64decode(x + x_padding)
                        return ed25519.Ed25519PublicKey.from_public_bytes(public_key_bytes)
            
            return None
            
        except Exception:
            return None


def load_roaming_config(config_path: str) -> RoamingConfig:
    """Load roaming configuration from YAML file."""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        issuers = []
        for issuer_data in data.get("issuers", []):
            issuers.append(TrustAnchor(
                name=issuer_data["name"],
                iss=issuer_data["iss"],
                discovery=issuer_data["discovery"],
                realms_allowed=issuer_data["realms_allowed"],
                audience_allowed=issuer_data["audience_allowed"],
                max_ttl_seconds=issuer_data["max_ttl_seconds"]
            ))
        
        return RoamingConfig(
            version=data.get("version", 1),
            issuers=issuers
        )
        
    except Exception as e:
        raise RoamingPassError(f"Failed to load roaming config: {e}")


def generate_ed25519_keypair() -> Tuple[ed25519.Ed25519PrivateKey, ed25519.Ed25519PublicKey]:
    """Generate Ed25519 keypair for roaming pass signing."""
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    return private_key, public_key


def create_roaming_receipt_block(claims: Dict[str, Any], verified: bool) -> Dict[str, Any]:
    """Create roaming block for receipt."""
    roaming_block = {
        "iss": claims.get("iss"),
        "sub": claims.get("sub"),
        "aud": claims.get("aud"),
        "realm_src": claims.get("realm_src"),
        "realm_dst": claims.get("realm_dst"),
        "scope": claims.get("scope", []),
        "jti": claims.get("jti"),
        "verified": verified
    }
    
    # Format expiration as ISO string if present
    if "exp" in claims:
        exp_dt = datetime.fromtimestamp(claims["exp"], tz=timezone.utc)
        roaming_block["exp"] = exp_dt.isoformat()
    
    return roaming_block


# HEL Integration Functions
def roaming_valid(claims: Dict[str, Any]) -> bool:
    """HEL predicate: roaming.valid"""
    return claims.get("verified", False) is True


def roaming_scope_contains(claims: Dict[str, Any], operation: str) -> bool:
    """HEL predicate: roaming.scope_contains(operation)"""
    return operation in claims.get("scope", [])


def roaming_realm_dst_matches(claims: Dict[str, Any], expected_realm: str) -> bool:
    """HEL predicate: roaming.realm_dst == expected_realm"""
    return claims.get("realm_dst") == expected_realm
