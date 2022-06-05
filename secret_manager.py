from google.cloud import secretmanager
import utils

def get_secret_key(secret_name: str) -> str:
    """Get secret key from secret manager for given secret name.

    Args:
        secret_name (str): Name of secret
    """
    if not secret_name:
        raise ValueError('secret name can not be empty.')

    # Setup the Secret manager Client
    client = secretmanager.SecretManagerServiceClient()
    
    # Get project id from enviornment
    project_id = utils.get_project_id()

    # Get secret key from secret manager
    request = {"name": f"projects/{project_id}/secrets/{secret_name}/versions/latest"}
    response = client.access_secret_version(request)
    return response.payload.data.decode("UTF-8")
