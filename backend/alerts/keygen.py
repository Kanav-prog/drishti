import os
import logging
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_master_key():
    """Generates the DARPA-grade Ed25519 signing key for DRISHTI Alerts."""
    key_path = os.path.join(os.path.dirname(__file__), "drishti_master.pem")
    
    if os.path.exists(key_path):
        logger.info(f"Master key already exists at {key_path}")
        return
        
    private_key = ed25519.Ed25519PrivateKey.generate()
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    with open(key_path, "wb") as f:
        f.write(pem)
        
    logger.info(f"Successfully generated new Ed25519 Master Key at: {key_path}")
    
if __name__ == "__main__":
    generate_master_key()
