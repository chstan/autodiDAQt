import os
import slack

__all__ = ('send_slack_message',)

def send_slack_message(msg, app, to=None):
    """
    Sends a Slack message to a particular user or channel. In order to use this,
    you will need to create and enable a bot for your user or group.

    Additionally, the token `SLACK_TOKEN` will need to be set to hold the
    API token you will generate through the online configuration flow.

    We recommend using `python-dotenv` to manage your dependencies, and in
    particular if a `.dotenv` is located with your app, we will load it for you.
    :param msg:
    :param to:
    :return:
    """
    token = os.environ['SLACK_TOKEN']
    client = slack.WebClient(token=token)

    if to is None:
        to = app.config.default_slack_channel

    client.chat_postMessage(channel=to, text=msg)