"""Streamlit integration checks with an explicitly selected upload supplied by the test."""
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


class Upload:
    def __init__(self, data, name="groceries.csv"):
        self.name, self.data = name, data

    def getvalue(self):
        return self.data


def choose(at, page):
    at.radio(key="page").set_value(page).run()
    assert not at.exception
    return at


def test_empty_app_waits_for_upload():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not at.exception
    assert "analysis" not in at.session_state
    assert any("Bring in your sales baskets" in x.value for x in at.header)


def test_all_pages_and_stale_settings():
    upload = Upload((ROOT / "Dataset/groceries.csv").read_bytes())
    with patch("streamlit.file_uploader", return_value=upload):
        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
        assert not at.exception and not at.error
        choose(at, "Mine patterns")
        at.button(key="run_analysis").click().run()
        assert not at.exception and not at.error
        assert len(at.session_state["analysis"]["rules"]) == 170
        choose(at, "Explore rules")
        choose(at, "Basket recommendations")
        at.button(key="suggest").click().run()
        assert not at.exception and not at.error
        assert at.session_state["recommendations"].Product.tolist() == ["yogurt", "other vegetables"]
        choose(at, "Evaluation")
        for button in ("benchmark", "sensitivity", "holdout"):
            at.button(key=button).click().run()
            assert not at.exception and not at.error
        assert at.session_state["evaluation"]["holdout"].Pass.sum() == 8
        choose(at, "Download results")
        at.button(key="prepare_export").click().run()
        assert not at.exception and not at.error
        assert len(at.session_state["archive"]) > 1000
        choose(at, "Project guide")
        choose(at, "Mine patterns")
        at.slider(key="confidence_pct").set_value(60.).run()
        assert "analysis" not in at.session_state
        assert "archive" not in at.session_state
        at.button(key="run_analysis").click().run()
        assert not at.exception and not at.error
        assert at.session_state["analysis"]["rules"].empty


def test_invalid_upload_has_friendly_message():
    with patch("streamlit.file_uploader", return_value=Upload(b'', "empty.csv")):
        at = AppTest.from_file(str(ROOT / "app.py")).run()
        assert not at.exception
        assert len(at.error) == 1
        assert "empty" in at.error[0].value


def test_replaced_upload_clears_results():
    upload = Upload((ROOT / "Dataset/groceries.csv").read_bytes())
    with patch("streamlit.file_uploader", return_value=upload):
        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
        choose(at, "Mine patterns")
        at.button(key="run_analysis").click().run()
        assert "analysis" in at.session_state
        upload.data = b'not,the,right,dataset'
        at.run()
        assert not at.exception and len(at.error) == 1
        assert "analysis" not in at.session_state


def test_live_chart_controls_and_recommendations_update():
    upload = Upload((ROOT / "Dataset/groceries.csv").read_bytes())
    with patch("streamlit.file_uploader", return_value=upload):
        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
        choose(at, "Mine patterns")
        at.button(key="run_analysis").click().run()
        choose(at, "Live charts")
        assert not at.error
        at.slider(key="chart_products").set_value(25).run()
        at.slider(key="chart_conf").set_value(90.).run()
        assert not at.exception and not at.error
        assert any("No rules meet" in x.value for x in at.markdown)
        at.slider(key="chart_conf").set_value(25.).run()
        assert not at.exception
        choose(at, "Basket recommendations")
        assert at.session_state["recommendations"].Product.tolist() == ["yogurt", "other vegetables"]
        at.multiselect(key="basket").set_value(["curd", "whole milk", "yogurt"]).run()
        assert not at.exception and not at.error
        assert "yogurt" not in at.session_state["recommendations"].Product.tolist()
        at.multiselect(key="basket").set_value([]).run()
        assert not at.exception and not at.error
        assert "recommendations" not in at.session_state


def test_replay_step_start_pause_reset_and_leave_page():
    upload = Upload((ROOT / "Dataset/groceries.csv").read_bytes())
    with patch("streamlit.file_uploader", return_value=upload):
        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
        choose(at, "Mine patterns")
        at.button(key="run_analysis").click().run()
        choose(at, "Live stream (simulation)")
        assert at.session_state["live_cursor"] == 0
        at.button(key="stream_next").click().run()
        assert not at.exception and not at.error
        assert at.session_state["live_cursor"] == 100
        at.button(key="stream_next").click().run()
        assert at.session_state["live_cursor"] == 200
        at.selectbox(key="stream_a").set_value("other vegetables").run()
        assert not at.exception and not at.error
        assert at.session_state["live_cursor"] == 200
        at.button(key="stream_start").click().run()
        assert not at.exception and at.session_state["live_running"]
        before = at.session_state["live_cursor"]
        # Simulate a due timer tick without waiting for a wall-clock browser event.
        at.session_state["live_last_tick"] = 0.
        at.run()
        assert not at.exception and at.session_state["live_cursor"] == before+100
        at.button(key="stream_pause").click().run()
        assert not at.exception and not at.session_state["live_running"]
        at.button(key="stream_reset").click().run()
        assert not at.exception and at.session_state["live_cursor"] == 0
        at.button(key="stream_start").click().run()
        choose(at, "Explore rules")
        assert not at.session_state["live_running"]
