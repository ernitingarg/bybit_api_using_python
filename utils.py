import os
import json

def get_project_id() -> str:
    """Get google cloud project id from deployment site or locally

    Raises:
        Exception: exception if not able to deletemine project id

    Returns:
        [type]: Return project id
    """
    # Deployed site
    # GCP_PROJECT is supported only with --runtime `python37`
    if 'GCP_PROJECT' in os.environ:
        return os.environ['GCP_PROJECT']
    # Local development
    elif 'GOOGLE_APPLICATION_CREDENTIALS' in os.environ:
        with open(os.environ['GOOGLE_APPLICATION_CREDENTIALS'], 'r') as fp:
           credentials = json.load(fp)
        return credentials['project_id']
    else:
        raise Exception('Failed to determine project_id')