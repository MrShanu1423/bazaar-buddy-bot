"""
Run this script ONCE on your local computer to get a YouTube refresh token.
Steps:
  1. pip install google-auth-oauthlib google-api-python-client
  2. python youtube_auth.py
  3. Browser opens → login with your YouTube account → allow access
  4. Copy the REFRESH TOKEN printed at the end
  5. Add it as GitHub Secret: YOUTUBE_REFRESH_TOKEN
"""
import json
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]

def main():
    flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
    creds = flow.run_local_server(port=0)

    print("\n" + "="*60)
    print("✅ Authorization successful!")
    print("="*60)
    print(f"\n📋 REFRESH TOKEN (copy this):\n{creds.refresh_token}")
    print(f"\n📋 ACCESS TOKEN:\n{creds.token}")
    print("\n" + "="*60)
    print("Now add YOUTUBE_REFRESH_TOKEN as a GitHub Secret!")
    print("="*60)

    with open("youtube_token.json", "w") as f:
        json.dump({
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": list(creds.scopes),
        }, f, indent=2)
    print("\n✅ Token also saved to youtube_token.json")

if __name__ == "__main__":
    main()
