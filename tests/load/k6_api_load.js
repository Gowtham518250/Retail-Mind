import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

const failures = new Rate("retail_mind_request_failures");
const requestDuration = new Trend("retail_mind_request_duration", true);

const baseUrl = (__ENV.BASE_URL || "").replace(/\/$/, "");
const targetPath = __ENV.TARGET_PATH || "/health/live";
const vus = Number.parseInt(__ENV.VUS || "10", 10);
const duration = __ENV.DURATION || "1m";
const thinkTime = Number.parseFloat(__ENV.THINK_TIME_SECONDS || "10");

export const options = {
  scenarios: {
    api_load: {
      executor: "constant-vus",
      vus,
      duration,
      gracefulStop: "30s",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<1000"],
    retail_mind_request_failures: ["rate<0.01"],
  },
};

export default function () {
  if (!baseUrl) {
    throw new Error("Set BASE_URL to the staging API URL before running this test.");
  }

  const headers = { Accept: "application/json" };
  if (__ENV.AUTH_TOKEN) {
    headers.Authorization = `Bearer ${__ENV.AUTH_TOKEN}`;
  }

  const response = http.get(`${baseUrl}${targetPath}`, {
    headers,
    tags: { endpoint: targetPath },
    timeout: __ENV.REQUEST_TIMEOUT || "10s",
  });

  const ok = check(response, {
    "response is 2xx or 3xx": (r) => r.status >= 200 && r.status < 400,
  });
  failures.add(!ok);
  requestDuration.add(response.timings.duration);

  if (thinkTime > 0) {
    sleep(thinkTime);
  }
}
