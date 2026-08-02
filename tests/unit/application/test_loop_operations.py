class FakeAdapter:
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []
        self.command_count = 0

    def execute_prompt(self, prompt):
        self.prompts.append(prompt)
        self.command_count += 1
        return self.responses.pop(0) if self.responses else "ok"


def test_popup_handler_allowlist_closes_without_login_or_purchase():
    from midscene_ui_agent.application.services.handlers import PopupHandler

    adapter = FakeAdapter(["closed"])
    outcome = PopupHandler(adapter).handle("close the popup; do not login, purchase, or submit data")
    assert outcome.succeeded
    assert adapter.command_count == 1


def test_episode_switch_and_feed_scroll_are_single_commands_with_verification():
    from midscene_ui_agent.application.services.handlers import EpisodeSwitcher, FeedScroller

    adapter = FakeAdapter(["tap next free episode", "assert new video playing", "swipe up once", "screenshot"])
    assert EpisodeSwitcher(adapter).switch(strategy="next_episode", require_free=True).succeeded
    assert FeedScroller(adapter).scroll_once().succeeded
    assert adapter.command_count == 4


def test_login_detection_returns_blocking_outcome():
    from midscene_ui_agent.application.services.handlers import PlaybackController

    outcome = PlaybackController(FakeAdapter(["login required"])).check()
    assert not outcome.succeeded and outcome.reason == "LOGIN_REQUIRED"
