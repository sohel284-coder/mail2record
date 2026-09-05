"""Gmail OAuth web flow — the "Connect with Google" button in Settings.

Needs the redirect URI (settings.GMAIL_OAUTH_REDIRECT_URI) registered as an
Authorized redirect URI on the Google Cloud OAuth client whose secrets live in
credentials/gmail_credentials.json.
"""

import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from .models import EmailAccount
from .providers import GMAIL_SCOPES

SESSION_STATE_KEY = "gmail_oauth_state"
SESSION_VERIFIER_KEY = "gmail_oauth_verifier"


def _require_gmail_oauth_enabled():
    if not settings.GMAIL_OAUTH_ENABLED:
        raise Http404("Gmail OAuth is disabled. Set GMAIL_OAUTH_ENABLED=True to use it.")


def _flow(state=None, code_verifier=None):
    return Flow.from_client_secrets_file(
        settings.GMAIL_OAUTH_CLIENT_SECRETS_FILE,
        scopes=GMAIL_SCOPES,
        redirect_uri=settings.GMAIL_OAUTH_REDIRECT_URI,
        state=state,
        code_verifier=code_verifier,
        autogenerate_code_verifier=code_verifier is None,
    )


@login_required
def gmail_oauth_start(request):
    _require_gmail_oauth_enabled()
    flow = _flow()
    auth_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent"
    )
    # The PKCE code_verifier is generated on this Flow instance; the callback
    # builds a fresh Flow, so it must be handed the same verifier or the token
    # exchange fails with "Missing code verifier".
    request.session[SESSION_STATE_KEY] = state
    request.session[SESSION_VERIFIER_KEY] = flow.code_verifier
    return redirect(auth_url)


@login_required
def gmail_oauth_callback(request):
    _require_gmail_oauth_enabled()
    if request.GET.get("error"):
        messages.error(request, f"Google sign-in was cancelled or failed ({request.GET['error']}).")
        return redirect("dashboard:settings")

    state = request.session.pop(SESSION_STATE_KEY, None)
    code_verifier = request.session.pop(SESSION_VERIFIER_KEY, None)
    flow = _flow(state=state, code_verifier=code_verifier)
    try:
        flow.fetch_token(authorization_response=request.build_absolute_uri())
    except Exception as exc:
        messages.error(request, f"Couldn't complete Google sign-in: {exc}")
        return redirect("dashboard:settings")

    creds = flow.credentials
    try:
        service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        email_address = service.users().getProfile(userId="me").execute().get("emailAddress", "")
    except Exception as exc:
        messages.error(request, f"Connected, but couldn't read the mailbox address: {exc}")
        return redirect("dashboard:settings")

    EmailAccount.objects.filter(user=request.user).delete()  # one mailbox per user
    account = EmailAccount(
        user=request.user,
        provider=EmailAccount.Provider.GMAIL,
        email_address=email_address,
        is_active=True,
    )
    account.credentials = json.loads(creds.to_json())
    account.save()

    messages.success(request, f"Gmail connected — {email_address}.")
    return redirect("dashboard:settings")
