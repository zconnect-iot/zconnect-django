from organizations.models import OrganizationUser
import pytest

from zconnect.models import OrganizationLogo
from zconnect.testutils.factories import OrganizationLogoFactory
from zconnect.testutils.helpers import paginated_body
from zconnect.testutils.util import model_to_dict

LOGO_PATH_BASE = "/files/download/"
LOGO_QUERY_STRING = "?name=zconnect.LogoImage%2Fbytes%2Ffilename%2Fmimetype%2F"
GREEN_LOGO = LOGO_PATH_BASE + LOGO_QUERY_STRING + "green_logo.png"
RED_LOGO = LOGO_PATH_BASE + LOGO_QUERY_STRING + "red_logo.png"

class TestGetOrgs:
    route = "/api/v3/organizations/"

    @pytest.mark.usefixtures("admin_login")
    def test_get_none(self, testclient):
        """Get an empty list of organizations"""
        expected = {
            "status_code": 200,
            "body": paginated_body([])
        }

        testclient.get_request_test_helper(expected)

    @pytest.mark.usefixtures("admin_login")
    def test_get_one(self, testclient, fake_org):
        """Get a single organization in a paginated body"""

        dumped = model_to_dict(fake_org)
        dumped["logo"] = None
        del dumped["created"]
        del dumped["modified"]
        expected = {
            "status_code": 200,
            "body": paginated_body([dumped])
        }

        testclient.get_request_test_helper(expected)


class TestGetOrg:
    route = "/api/v3/organizations/{org_id}"

    @pytest.mark.usefixtures("admin_login")
    def test_get_org_no_logo(self, testclient, fake_org):
        """Get a single organization without a logo"""

        dumped = model_to_dict(fake_org)
        dumped["logo"] = None
        del dumped["created"]
        del dumped["modified"]
        expected = {
            "status_code": 200,
            "body": dumped
        }
        params = {"org_id": fake_org.id}
        testclient.get_request_test_helper(expected, path_params=params)

    @pytest.mark.usefixtures("admin_login")
    def test_get_org_with_logo(self, testclient, fake_org):
        """Get a single organization with a logo"""

        OrganizationLogoFactory(organization=fake_org)
        dumped = model_to_dict(fake_org)
        dumped["logo"] = RED_LOGO
        del dumped["created"]
        del dumped["modified"]
        expected = {
            "status_code": 200,
            "body": dumped
        }
        params = {"org_id": fake_org.id}
        testclient.get_request_test_helper(expected, path_params=params)




class TestMembershipNoPermission:
    route = "/api/v3/organizations/{org_id}/membership"

    def test_no_permission(self, testclient, fake_org):
        """Access denied when reading organization membership"""

        path_params = {
            "org_id": fake_org.id,
        }
        expected = {
            "status_code": 401,
            "body": {
                "detail": "Authentication credentials were not provided.",
            }
        }
        testclient.get_request_test_helper(expected, path_params=path_params)


def membership_to_dict(membership, user):
    as_dict = model_to_dict(membership)

    del as_dict["modified"]
    del as_dict["organization"]

    as_dict["user"] = {
        "id": user.id,
        "email": user.email,
    }

    return as_dict


@pytest.mark.usefixtures("admin_login")
class TestOrganizationMembership:
    route = "/api/v3/organizations/{org_id}/membership"

    def test_no_members(self, testclient, fake_org):
        """Get an empty user list (paginated)"""

        path_params = {
            "org_id": fake_org.id,
        }
        expected = {
            "status_code": 200,
            "body": paginated_body([])
        }

        testclient.get_request_test_helper(expected, path_params=path_params)

    def test_one_member(self, testclient, joeseed, fake_org):
        """Get a list of one user (Joe Seed is a member of fake_org)"""
        membership = OrganizationUser.objects.filter(user=joeseed).get()

        as_dict = membership_to_dict(membership, joeseed)

        path_params = {
            "org_id": fake_org.id,
        }
        expected = {
            "status_code": 200,
            "body": paginated_body([as_dict])
        }

        testclient.get_request_test_helper(expected, path_params=path_params)

    def test_add_membership(self, testclient, fredbloggs, fake_org):
        """Fred bloggs is not a member - add him, check he's been added"""

        path_params = {
            "org_id": fake_org.id,
        }

        post_body = {
            "user": {
                "id": fredbloggs.id,
                "email": fredbloggs.email
            }
        }
        expected = {
            "status_code": 201,
            "body": {
                **post_body,
                "id": 1,
                "is_admin": False,
                "created": None,
            }
        }

        testclient.post_request_test_helper(post_body, expected,
                                            path_params=path_params)

        membership = OrganizationUser.objects.filter(user=fredbloggs).get()
        as_dict = membership_to_dict(membership, fredbloggs)

        expected = {
            "status_code": 200,
            "body": paginated_body([as_dict])
        }


        testclient.get_request_test_helper(expected, path_params=path_params)

    def test_add_membership_already_exists(self, testclient, joeseed, fake_org):
        """Can't be a member of an organization twice"""

        path_params = {
            "org_id": fake_org.id,
        }

        post_body = {
            "user": {
                "id": joeseed.id,
                "email": joeseed.email
            }
        }
        expected = {
            "status_code": 400,
            "body": {
                "detail": "That user is already a member of that Organization",
            }
        }

        testclient.post_request_test_helper(post_body, expected,
                                            path_params=path_params)


@pytest.mark.usefixtures("admin_login")
class TestSpecificOrganizationMembership:
    route = "/api/v3/organizations/{org_id}/membership/{membership_id}"

    def test_get_membership(self, testclient, joeseed, fake_org):
        """Get a single organization membership"""

        membership = OrganizationUser.objects.filter(user=joeseed).get()
        as_dict = membership_to_dict(membership, joeseed)
        path_params = {
            "org_id": fake_org.id,
            "membership_id": membership.id,
        }
        expected = {
            "status_code": 200,
            "body": as_dict,
        }
        testclient.get_request_test_helper(expected, path_params=path_params)

    def test_remove_membership(self, testclient, joeseed, fake_org):
        """Basically, remove a member from a organization"""
        membership = OrganizationUser.objects.filter(user=joeseed).get()

        path_params = {
            "org_id": fake_org.id,
            "membership_id": membership.id,
        }
        expected = {
            "status_code": 204,
        }

        testclient.delete_request_test_helper(expected, path_params=path_params)

    def test_cannot_update(self, testclient, joeseed, fake_org):
        """Should not be able to update a membership"""
        membership = OrganizationUser.objects.filter(user=joeseed).get()

        patch_body = {
            "user": 1,
        }
        path_params = {
            "org_id": fake_org.id,
            "membership_id": membership.id,
        }
        expected = {
            "status_code": 405,
            "body": {
                "detail": "Method \"PATCH\" not allowed."
            },
        }

        testclient.patch_request_test_helper(patch_body, expected,
                                             path_params=path_params)


@pytest.mark.usefixtures("admin_login")
class TestLogo:
    route = "/api/v3/organizations/{org_id}/logo/"

    def test_get_logo(self, testclient, fake_org, red_logo):
        """Get an organization logo"""
        OrganizationLogoFactory(organization=fake_org)
        params = {"org_id": fake_org.id}
        expected = {
            "status_code": 200,
            "body": {
                'id': 1,
                'image': RED_LOGO,
                'organization': 1
            }
        }
        testclient.get_request_test_helper(expected, path_params=params)

    def test_get_logo_404(self, testclient, fake_org):
        """Try to get the logo for an organization that doesn't have one"""
        params = {"org_id": fake_org.id}
        expected = {
            "status_code": 404,
            "body": {"detail": "Not found."}
        }
        testclient.get_request_test_helper(expected, path_params=params)

    def test_upload_logo(self, testclient, fake_org, red_logo):
        """Upload an organization logo"""

        body = {'image': red_logo}
        download_route = RED_LOGO
        expected = {
            "status_code": 200,
            "body": {
                "id": 1,
                "organization": fake_org.id,
                "image": download_route
            }
        }
        route = self.route.format(org_id=fake_org.id)
        result = testclient.django_client.post(route, body, format="multipart")
        testclient.print_response(result)
        testclient.assert_response_code(result, expected)
        testclient.check_expected_keys(expected, result, True, True)
        OrganizationLogo.objects.get(organization=fake_org)

    def test_upload_a_different_logo(self, testclient, fake_org, green_logo):
        """Upload a logo to an organization that already has one"""

        OrganizationLogoFactory(organization=fake_org)
        body = {'image': green_logo}
        download_route = GREEN_LOGO
        expected = {
            "status_code": 200,
            "body": {
                "id": 2,
                "organization": fake_org.id,
                "image": download_route
            }
        }
        route = self.route.format(org_id=fake_org.id)

        # Doing this manaully because of the format='multipart' which you can't
        # do with the test helpers
        result = testclient.django_client.post(route, body, format="multipart")

        testclient.print_response(result)
        testclient.assert_response_code(result, expected)
        testclient.check_expected_keys(expected, result, True, True)

    def test_delete_logo(self, testclient, fake_org):
        """Delete a logo and check it's gone"""

        OrganizationLogoFactory(organization=fake_org)
        # Delete the logo
        expected = {
            "status_code": 204,
            "body": {}
        }
        route = self.route.format(org_id=fake_org.id)
        result = testclient.django_client.delete(route)
        testclient.print_response(result)
        testclient.assert_response_code(result, expected)
        testclient.check_expected_keys(expected, result, True, True)

        matches = OrganizationLogo.objects.filter(organization=fake_org.id)
        assert not matches


class TestImageDownload:
    route = RED_LOGO

    def test_download_logo(self, testclient, fake_org):
        """Download a logo and check the file type"""

        OrganizationLogoFactory(organization=fake_org)

        # Download the file and check it's right
        download = testclient.django_client.get(self.route)
        disposition = "attachment; filename=red_logo.png"
        assert download.get("Content-Disposition") == disposition


@pytest.mark.usefixtures("admin_login")
class TestOrgMembershipByUser:
    route = "/api/v3/organizations/{org_id}/user"

    def test_no_members(self, testclient, fake_org):
        """Organization has no members"""

        path_params = {
            "org_id": fake_org.id,
        }
        expected = {
            "status_code": 200,
            "body": paginated_body([])
        }
        testclient.get_request_test_helper(expected, path_params=path_params)

    def test_one_member(self, testclient, joeseed, fake_org):
        """Joeseed is a member of fake_org in the fixtures"""

        membership = OrganizationUser.objects.filter(user=joeseed).get()
        as_dict = membership_to_dict(membership, joeseed)
        path_params = {
            "org_id": fake_org.id,
        }
        expected = {
            "status_code": 200,
            "body": paginated_body([as_dict])
        }
        testclient.get_request_test_helper(expected, path_params=path_params)


@pytest.mark.usefixtures("admin_login")
class TestSpecificOrgMembershipByUser:
    route = "/api/v3/organizations/{org_id}/user/{user_id}"

    def test_get_membership(self, testclient, joeseed, fake_org):
        """Get membership using user id as the lookup field"""

        membership = OrganizationUser.objects.filter(user=joeseed).get()
        as_dict = membership_to_dict(membership, joeseed)
        path_params = {
            "org_id": fake_org.id,
            "user_id": joeseed.id,
        }
        expected = {
            "status_code": 200,
            "body": as_dict,
        }
        testclient.get_request_test_helper(expected, path_params=path_params)

    def test_remove_membership(self, testclient, joeseed, fake_org):
        """Basically, remove a member from a organization"""

        OrganizationUser.objects.filter(user=joeseed).get()
        path_params = {
            "org_id": fake_org.id,
            "user_id": joeseed.id,
        }
        expected = {
            "status_code": 204,
        }
        testclient.delete_request_test_helper(expected, path_params=path_params)

    def test_cannot_update(self, testclient, joeseed, fake_org):
        """Should not be able to update a membership"""

        OrganizationUser.objects.filter(user=joeseed).get()
        patch_body = {
            "user": 1,
        }
        path_params = {
            "org_id": fake_org.id,
            "user_id": joeseed.id,
        }
        expected = {
            "status_code": 405,
            "body": {
                "detail": "Method \"PATCH\" not allowed."
            },
        }
        testclient.patch_request_test_helper(patch_body, expected,
                                             path_params=path_params)
