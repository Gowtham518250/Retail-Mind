import http from "k6/http";
import { check, sleep } from "k6";

function positiveInt(name, fallback) {
  const parsed = Number.parseInt(__ENV[name] || String(fallback), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

const baseUrl = (__ENV.API_BASE_URL || "").replace(/\/+$/, "");
const path = __ENV.READ_PATH || "/health/ready";
const targetVUs = positiveInt("TARGET_VUS", 25);
const expectedStatus = positiveInt("EXPECTED_STATUS", 200);
const thinkSeconds = Number.parseFloat(__ENV.THINK_TIME_SECONDS || "1");

if (!baseUrl) {
  throw new Error("Set API_BASE_URL to the dedicated staging API URL.");
}

const headers = { Accept: "application/json" };
if (__ENV.API_BEARER_TOKEN) {
  headers.Authorization = `Bearer ${__ENV.API_BEARER_TOKEN}`;
}

export const options = {
  stages: [
    { duration: __ENV.RAMP_DURATION || "1m", target: targetVUs },
    { duration: __ENV.HOLD_DURATION || "2m", target: targetVUs },
    { duration: __ENV.COOLDOWN_DURATION || "1m", target: 0 },
  ],
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<800", "p(99)<1500"],
    checks: ["rate>0.99"],
  },
};

export default function () {
  const response = http.get(`${baseUrl}${path}`, {
    headers,
    timeout: __ENV.REQUEST_TIMEOUT || "10s",
    tags: { path },
  });
  check(response, {
    [`status is ${expectedStatus}`]: (res) => res.status === expectedStatus,
  });
  sleep(Number.isFinite(thinkSeconds) && thinkSeconds >= 0 ? thinkSeconds : 1);
}
