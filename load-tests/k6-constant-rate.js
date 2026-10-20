import http from "k6/http";
import { check } from "k6";

function positiveInt(name, fallback) {
  const parsed = Number.parseInt(__ENV[name] || String(fallback), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

const baseUrl = (__ENV.API_BASE_URL || "").replace(/\/+$/, "");
const path = __ENV.READ_PATH || "/health/ready";
const targetRps = positiveInt("TARGET_RPS", 10);
const expectedStatus = positiveInt("EXPECTED_STATUS", 200);
const preAllocatedVUs = positiveInt("PRE_ALLOCATED_VUS", Math.max(20, targetRps * 2));
const maxVUs = positiveInt("MAX_VUS", Math.max(100, targetRps * 5));

if (!baseUrl) {
  throw new Error("Set API_BASE_URL to the dedicated staging API URL.");
}

const headers = { Accept: "application/json" };
if (__ENV.API_BEARER_TOKEN) {
  headers.Authorization = `Bearer ${__ENV.API_BEARER_TOKEN}`;
}

export const options = {
  scenarios: {
    constant_rate: {
      executor: "constant-arrival-rate",
      rate: targetRps,
      timeUnit: "1s",
      duration: __ENV.DURATION || "1m",
      preAllocatedVUs,
      maxVUs,
    },
  },
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
}
