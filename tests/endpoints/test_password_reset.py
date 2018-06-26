from django.conf import settings
from django.core import mail


class TestPasswordReset:
    route = "/api/v3/auth/password/reset/"

    def test_reset(self, testclient, joeseed):
        """Puts email in the 'memory' outbox"""
        post_body = {
            "email": joeseed.email
        }

        expected = {
            "status_code": 200,
            "body": {
                "detail": "Password reset e-mail has been sent."
            }
        }

        assert len(mail.outbox) == 0

        testclient.post_request_test_helper(post_body, expected)

        site_name = getattr(settings, 'FRONTEND_DOMAIN')

        assert len(mail.outbox) == 1
        email = mail.outbox[0]
        assert email.subject == "Password reset on {}".format(site_name)
        print(email.body)
        assert "uid=" in email.body
        assert "token=" in email.body

    def test_reset_nonexistent(self, testclient):
        """It will say a password reset email has been sent even if they put in
        a bad email
        """
        post_body = {
            "email": "aokelelerkigjbeueuurhh@blaaairohuh.com"
        }

        expected = {
            "status_code": 200,
            "body": {
                "detail": "Password reset e-mail has been sent."
            }
        }

        assert len(mail.outbox) == 0

        testclient.post_request_test_helper(post_body, expected)

        assert len(mail.outbox) == 0
