# Standard Imports
import unittest
from unittest import mock
import asyncio


# Internal Imports
import slack
from tests.helpers import (
    mock_response,
    async_test,
    fake_req_args,
    AsyncMock,
    mock_request,
)
import slack.errors as err


@mock.patch("slack.WebClient._request", new_callable=mock_request)
class TestWebClient(unittest.TestCase):
    def setUp(self):
        self.client = slack.WebClient("xoxb-abc-123", loop=asyncio.get_event_loop())

    def tearDown(self):
        pass

    def test_api_calls_return_a_response_when_run_in_sync_mode(self, mock_request):
        resp = self.client.api_test()
        self.assertFalse(asyncio.isfuture(resp))
        self.assertTrue(resp["ok"])

    @async_test
    async def test_api_calls_return_a_future_when_run_in_async_mode(self, mock_request):
        self.client.run_async = True
        future = self.client.api_test()
        self.assertTrue(asyncio.isfuture(future))
        resp = await future
        self.assertTrue(resp["ok"])

    def test_builtin_api_methods_send_json(self, mock_request):
        self.client.api_test(msg="bye")
        mock_request.assert_called_once_with(
            http_verb="POST",
            api_url="https://www.slack.com/api/api.test",
            req_args=fake_req_args(json={"msg": "bye"}),
        )

    def test_requests_can_be_paginated(self, mock_request):
        mock_request.response.side_effect = [
            {
                "data": {
                    "ok": True,
                    "members": ["Bob", "cat"],
                    "response_metadata": {"next_cursor": 1},
                },
                "status_code": 200,
                "headers": {},
            },
            {
                "data": {"ok": True, "members": ["Kevin", "dog"]},
                "status_code": 200,
                "headers": {},
            },
        ]

        users = []
        for page in self.client.users_list(limit=2):
            users = users + page["members"]
        self.assertTrue(len(users) == 4)

    def test_request_pagination_stops_when_next_cursor_is_missing(self, mock_request):
        mock_request.response.side_effect = [
            {
                "data": {"ok": True, "members": ["Bob", "cat"]},
                "status_code": 200,
                "headers": {},
            },
            {
                "data": {"ok": True, "members": ["Kevin", "dog"]},
                "status_code": 200,
                "headers": {},
            },
        ]

        users = []
        for page in self.client.users_list(limit=2):
            users = users + page["members"]
        self.assertTrue(len(users) == 2)
        mock_request.assert_called_once_with(
            http_verb="GET",
            api_url="https://www.slack.com/api/users.list",
            req_args=fake_req_args(params={"limit": 2}),
        )

    def test_xoxb_token_validation(self, mock_request):
        with self.assertRaises(err.BotUserAccessError):
            # Channels can only be created with xoxa tokens.
            self.client.channels_create("test")

    def test_json_can_only_be_sent_with_post_requests(self, mock_request):
        with self.assertRaises(err.SlackRequestError):
            self.client.api_call("fake.method", http_verb="GET", json={})

    def test_slack_api_error_is_raised_on_unsuccessful_responses(self, mock_request):
        mock_request.response.side_effect = [
            {"data": {"ok": False}, "status_code": 200, "headers": {}},
            {"data": {"ok": True}, "status_code": 500, "headers": {}},
        ]
        with self.assertRaises(err.SlackApiError):
            self.client.api_test()
        with self.assertRaises(err.SlackApiError):
            self.client.api_test()

    @mock.patch("aiohttp.FormData.add_field")
    def test_the_api_call_files_argument_creates_the_expected_data(
        self, mock_add_field, mock_request
    ):
        self.client.token = "xoxa-123"
        with mock.patch("builtins.open", mock.mock_open(read_data="fake")):
            self.client.users_setPhoto(image="/fake/path")

        mock_add_field.assert_called_once_with("image", mock.ANY)
        mock_request.assert_called_once_with(
            http_verb="POST",
            api_url="https://www.slack.com/api/users.setPhoto",
            req_args=fake_req_args(),
        )

    @mock.patch("aiohttp.FormData.add_field")
    def test_the_api_call_files_argument_combines_with_additional_data(
        self, mock_add_field, mock_request
    ):
        self.client.token = "xoxa-123"
        with mock.patch("builtins.open", mock.mock_open(read_data="fake")) as mock_file:
            self.client.users_setPhoto(image=mock_file(), name="photo")

        mock_add_field.assert_has_calls(
            [mock.call("image", mock.ANY), mock.call("name", "photo")]
        )
