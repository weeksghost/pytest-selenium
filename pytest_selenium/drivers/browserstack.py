# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from py.xml import html
import pytest

import allure

from pytest_selenium.drivers.cloud import Provider


class BrowserStack(Provider):

    API = "https://www.browserstack.com/automate/sessions/{session}.json"
    JOB = "https://api.browserstack.com/automate/sessions/{session}"

    @property
    def auth(self):
        return self.username, self.key

    @property
    def executor(self):
        return "https://hub.browserstack.com/wd/hub"

    @property
    def username(self):
        return self.get_credential(
            "username", ["BROWSERSTACK_USERNAME", "BROWSERSTACK_USR"]
        )

    @property
    def key(self):
        return self.get_credential(
            "key", ["BROWSERSTACK_ACCESS_KEY", "BROWSERSTACK_PSW"]
        )


@pytest.mark.optionalhook
def pytest_selenium_runtest_makereport(item, report, summary, extra):
    provider = BrowserStack()
    if not provider.uses_driver(item.config.getoption("driver")):
        return

    passed = report.passed or (report.failed and hasattr(report, "wasxfail"))
    session_id = item._driver.session_id
    api_url = provider.API.format(session=session_id)
    api_endpoint = provider.JOB.format(session=session_id)

    # lazy import requests for projects that don't need requests
    import requests

    try:
        job_info = requests.get(api_url, auth=provider.auth, timeout=10).json()
        job_url = job_info["automation_session"]["browser_url"]
        # Add the job URL to the summary
        summary.append("{0} Job: {1}".format(provider.name, job_url))
        pytest_html = item.config.pluginmanager.getplugin("html")
        # Add the job URL to the HTML report
        extra.append(pytest_html.extras.url(job_url, "{0} Job".format(provider.name)))

    except Exception as e:
        summary.append(
            "WARNING: Failed to determine {0} job URL: {1}".format(provider.name, e)
        )

    try:
        # Update the job result
        job_status = job_info["automation_session"]["status"]
        status = "running" if passed else "error"
        if report.when == "teardown" and passed:
            status = "completed"
        if job_status not in ("error", status):
            # Only update the result if it's not already marked as failed
            requests.put(
                api_url,
                headers={"Content-Type": "application/json"},
                params={"status": status},
                auth=provider.auth,
                timeout=10,
            )
    except Exception as e:
        summary.append("WARNING: Failed to update job status: {0}".format(e))


    # Add video results to the summary
    video = requests.get(api_endpoint, auth=provider.auth, timeout=10,).json().get('automation_session').get('video_url')
    if video == None:
        pass
    else:
        summary.append(_video_html(video, session_id))
        pytest_html = item.config.pluginmanager.getplugin("html")
        extra.append(pytest_html.extras.html(_video_html(video, session_id)))
        vid_markup = _video_html(video, session_id)
        allure.attach(vid_markup, name='Video', attachment_type=allure.attachment_type.HTML)

    # Add the job URL to Allure results
    #if job_url == None:
    #    pass
    #else:
    #    job_url_markup = _job_html(job_url)
    #    allure.attach(job_url_markup, name='Browserstack URL', attachment_type=allure.attachment_type.HTML)


def driver_kwargs(request, test, capabilities, **kwargs):
    provider = BrowserStack()
    capabilities.setdefault("name", test)
    capabilities.setdefault("browserstack.user", provider.username)
    capabilities.setdefault("browserstack.key", provider.key)
    kwargs = {
        "command_executor": provider.executor,
        "desired_capabilities": capabilities,
    }
    return kwargs


def _video_html(video, session):
    return str(
        html.div(
            html.video(
                html.source(src=video, type="video/mp4"),
                width="100%",
                height="100%",
                controls="controls",
            ),
            id="mediaplayer{session}".format(session=session),
            style="margin-left:5px; overflow:hidden;",
        )
    )


def _job_html(url):
    return str(
        html.div(
            html.a(
                "BrowserStack Results",
                href=url,
                style="font-family: Helvetica, Arial, sans-serif; color: #000;",
                target="_blank",
            )
        )
    )
